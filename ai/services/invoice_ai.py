import json
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from expenses.models import Expense
from invoice.models import Invoice
from reports.services import monthly_report, tax_summary

from .openai_service import OpenAIServiceError, generate_json_response


def _to_float(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _safe_number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _serialize_recent_invoices(business):
    recent_invoices = (
        Invoice.objects.filter(business=business)
        .order_by("-created_at")
        .prefetch_related("receipts")
    )[:5]

    return [
        {
            "invoice_number": invoice.invoice_number,
            "client_name": invoice.client_name,
            "status": invoice.status,
            "issue_date": invoice.issue_date.isoformat(),
            "due_date": invoice.due_date.isoformat(),
            "total_amount": _to_float(invoice.total_amount),
            "amount_paid": _to_float(invoice.amount_paid),
            "balance_due": _to_float(invoice.balance_due),
            "currency": invoice.currency,
        }
        for invoice in recent_invoices
    ]


def _serialize_recent_expenses(business):
    recent_expenses = (
        Expense.objects.filter(business=business)
        .select_related("category")
        .order_by("-expense_date")
    )[:5]

    return [
        {
            "title": expense.title,
            "category": expense.category.name if expense.category else "Uncategorized",
            "amount": _to_float(expense.amount),
            "total_amount": _to_float(expense.total_amount),
            "tax_deductible": expense.tax_deductible,
            "expense_date": expense.expense_date.isoformat(),
        }
        for expense in recent_expenses
    ]


def _build_business_snapshot(business):
    today = timezone.localdate()
    invoice_queryset = Invoice.objects.filter(business=business).prefetch_related("receipts")
    expense_queryset = Expense.objects.filter(business=business)

    outstanding_invoices = [invoice for invoice in invoice_queryset if invoice.balance_due > Decimal("0.00")]
    overdue_invoices = [
        invoice
        for invoice in outstanding_invoices
        if invoice.due_date and invoice.due_date < today
    ]

    paid_income = sum(
        (invoice.total_amount for invoice in invoice_queryset.filter(status="paid")),
        Decimal("0.00"),
    )
    total_expenses = sum((expense.total_amount for expense in expense_queryset), Decimal("0.00"))

    return {
        "business": {
            "id": business.id,
            "name": business.display_name or business.name,
            "email": business.email,
            "phone": business.phone,
            "tax_rate": _to_float(business.tax_rate),
        },
        "dashboard": {
            "paid_income": _to_float(paid_income),
            "total_expenses": _to_float(total_expenses),
            "outstanding_invoice_count": len(outstanding_invoices),
            "outstanding_balance": _to_float(
                sum((invoice.balance_due for invoice in outstanding_invoices), Decimal("0.00"))
            ),
            "overdue_invoice_count": len(overdue_invoices),
        },
        "current_month_report": monthly_report(business, today.month, today.year),
        "tax_summary": tax_summary(business, today.year),
        "recent_invoices": _serialize_recent_invoices(business),
        "recent_expenses": _serialize_recent_expenses(business),
    }


def _default_invoice_draft():
    today = timezone.localdate()
    return {
        "client_name": "",
        "client_email": "",
        "issue_date": today.isoformat(),
        "due_date": (today + timedelta(days=30)).isoformat(),
        "items": [
            {
                "description": "",
                "quantity": 1,
                "unit_price": 0,
            }
        ],
        "status": "draft",
    }


def _normalize_invoice_draft(payload, business=None):
    draft = _default_invoice_draft()
    if not isinstance(payload, dict):
        if business:
            draft["business_id"] = business.id
        return draft

    draft["client_name"] = str(payload.get("client_name") or payload.get("customer_name") or "").strip()
    draft["client_email"] = str(payload.get("client_email") or "").strip()
    draft["issue_date"] = str(payload.get("issue_date") or draft["issue_date"])
    draft["due_date"] = str(payload.get("due_date") or draft["due_date"])
    draft["status"] = "draft"

    items = payload.get("items")
    if isinstance(items, list) and items:
        normalized_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description") or item.get("name") or "").strip()
            quantity = _safe_number(item.get("quantity") or 1, 1)
            unit_price = _safe_number(item.get("unit_price") or item.get("price") or 0, 0)
            normalized_items.append(
                {
                    "description": description,
                    "quantity": max(float(quantity), 1),
                    "unit_price": max(float(unit_price), 0),
                }
            )
        if normalized_items:
            draft["items"] = normalized_items

    if business:
        draft["business_id"] = business.id
        draft["currency"] = "KES"

    return draft


def _normalize_report_summary(payload, business=None):
    if not isinstance(payload, dict):
        return None

    metrics = payload.get("metrics")
    normalized_metrics = []
    if isinstance(metrics, list):
        for metric in metrics[:4]:
            if not isinstance(metric, dict):
                continue
            normalized_metrics.append(
                {
                    "label": str(metric.get("label") or "").strip(),
                    "value": str(metric.get("value") or "").strip(),
                    "tone": str(metric.get("tone") or "neutral").strip() or "neutral",
                }
            )

    insights = payload.get("insights") if isinstance(payload.get("insights"), list) else []
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []

    if not normalized_metrics and business:
        snapshot = _build_business_snapshot(business)
        current_month = snapshot["current_month_report"]
        normalized_metrics = [
            {"label": "Income", "value": f"KES {current_month['total_income']:,.2f}", "tone": "positive"},
            {"label": "Expenses", "value": f"KES {current_month['total_expenses']:,.2f}", "tone": "warning"},
            {"label": "Tax Owed", "value": f"KES {current_month['tax_owed']:,.2f}", "tone": "negative"},
        ]

    return {
        "period_label": str(payload.get("period_label") or "Current business snapshot").strip(),
        "headline": str(payload.get("headline") or "").strip(),
        "metrics": normalized_metrics,
        "insights": [str(item).strip() for item in insights if str(item).strip()][:4],
        "actions": [str(item).strip() for item in actions if str(item).strip()][:4],
    }


def _normalize_assistant_payload(payload, business=None):
    if not isinstance(payload, dict):
        raise OpenAIServiceError("AI assistant returned an unexpected response format.")

    return {
        "intent": str(payload.get("intent") or "general").strip() or "general",
        "reply": str(payload.get("reply") or "").strip(),
        "invoice_draft": _normalize_invoice_draft(payload.get("invoice_draft"), business)
        if payload.get("invoice_draft")
        else None,
        "report_summary": _normalize_report_summary(payload.get("report_summary"), business)
        if payload.get("report_summary")
        else None,
        "suggested_prompts": [
            str(item).strip()
            for item in payload.get("suggested_prompts", [])
            if str(item).strip()
        ][:4],
    }


def generate_assistant_response(prompt, business=None, mode="auto"):
    system_prompt = """
You are SmartInvoice AI Copilot for a small-business finance platform.
You help with invoice drafting, financial summaries, payments guidance, tax context, and workflow suggestions.

Return valid JSON only with this exact shape:
{
  "intent": "invoice" | "report" | "general",
  "reply": "short helpful human response",
  "invoice_draft": {
    "client_name": "",
    "client_email": "",
    "issue_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD",
    "items": [
      {"description": "", "quantity": 1, "unit_price": 0}
    ]
  } | null,
  "report_summary": {
    "period_label": "",
    "headline": "",
    "metrics": [
      {"label": "", "value": "", "tone": "positive|warning|negative|neutral"}
    ],
    "insights": ["", ""],
    "actions": ["", ""]
  } | null,
  "suggested_prompts": ["", "", ""]
}

Rules:
- If the user is asking to create or draft an invoice, set intent to "invoice" and fill invoice_draft.
- If the user is asking about reports, cash flow, expenses, tax, profit, or performance, set intent to "report" and fill report_summary.
- Keep reply concise, practical, and tailored to the supplied business context.
- Do not invent unavailable business facts. Use the provided context only.
""".strip()

    user_payload = {
        "mode": mode,
        "prompt": prompt,
        "business_context": _build_business_snapshot(business) if business else None,
    }
    ai_payload = generate_json_response(system_prompt, json.dumps(user_payload, default=str))
    normalized_payload = _normalize_assistant_payload(ai_payload, business)

    if mode == "invoice" and not normalized_payload["invoice_draft"]:
        normalized_payload["invoice_draft"] = _normalize_invoice_draft({}, business)
    if mode == "report" and not normalized_payload["report_summary"] and business:
        normalized_payload["report_summary"] = _normalize_report_summary({}, business)

    if not normalized_payload["reply"]:
        normalized_payload["reply"] = (
            "I reviewed your prompt and prepared the best structured answer I could from the current business data."
        )

    return normalized_payload


def generate_invoice_from_text(user_input):
    payload = generate_assistant_response(user_input, business=None, mode="invoice")
    return payload.get("invoice_draft") or _normalize_invoice_draft({})
