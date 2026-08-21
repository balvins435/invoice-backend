from django.http import FileResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from expenses.serializers import ExpenseSerializer
from invoice.serializers import InvoiceSerializer

from .services import monthly_report, monthly_reports_for_year, tax_summary
from .utils import generate_report_pdf
from .selectors import dashboard_data, resolve_business


class BusinessScopedReportMixin:
    missing_business_message = "Select a business to continue."

    def _resolve_business(self, request):
        business_id = request.query_params.get("business") or request.query_params.get("business_id")
        return resolve_business(user=request.user, business_id=business_id, missing_message=self.missing_business_message)


class MonthlyReportAPIView(BusinessScopedReportMixin, APIView):
    permission_classes = [IsAuthenticated]
    missing_business_message = "Select a business to view this report."

    def get(self, request):
        business = self._resolve_business(request)
        month = request.query_params.get("month")
        year = int(request.query_params.get("year") or timezone.now().year)

        if not business:
            return Response({"error": "No business found for this user"}, status=400)

        if month:
            report = monthly_report(
                business=business,
                month=int(month),
                year=year,
            )
            return Response(report)

        report = monthly_reports_for_year(business=business, year=year)
        return Response(report)


class TaxSummaryAPIView(BusinessScopedReportMixin, APIView):
    permission_classes = [IsAuthenticated]
    missing_business_message = "Select a business to view this tax summary."

    def get(self, request):
        business = self._resolve_business(request)
        year = int(request.query_params.get("year") or timezone.now().year)
        month = request.query_params.get("month")

        if not business:
            return Response({"error": "No business found for this user"}, status=400)

        return Response(
            tax_summary(
                business=business,
                year=year,
                month=int(month) if month else None,
            )
        )


class DashboardStatsAPIView(BusinessScopedReportMixin, APIView):
    permission_classes = [IsAuthenticated]
    missing_business_message = "Select a business to view this dashboard."

    def _empty_payload(self):
        return {
            "total_income": 0,
            "total_expenses": 0,
            "net_profit": 0,
            "pending_invoices": 0,
            "overdue_invoices": 0,
            "total_clients": 0,
            "recent_invoices": [],
            "recent_expenses": [],
            "monthly_trends": [],
        }

    def get(self, request):
        business = self._resolve_business(request)
        if not business:
            return Response(self._empty_payload())

        data = dashboard_data(business)
        all_invoices, expenses = data["invoices"], data["expenses"]
        total_income, total_expenses = data["total_income"], data["total_expenses"]

        recent_invoices = InvoiceSerializer(
            all_invoices.order_by("-created_at")[:5],
            many=True,
            context={"request": request},
        ).data
        recent_expenses = ExpenseSerializer(
            expenses.order_by("-created_at")[:5],
            many=True,
            context={"request": request},
        ).data

        return Response(
            {
                "total_income": float(total_income),
                "total_expenses": float(total_expenses),
                "net_profit": float(total_income - total_expenses),
                "pending_invoices": data["pending_invoices"],
                "overdue_invoices": data["overdue_invoices"],
                "total_clients": data["total_clients"],
                "recent_invoices": recent_invoices,
                "recent_expenses": recent_expenses,
                "monthly_trends": monthly_reports_for_year(
                    business=business,
                    year=timezone.now().year,
                ),
            }
        )


class ReportPDFAPIView(BusinessScopedReportMixin, APIView):
    permission_classes = [IsAuthenticated]
    missing_business_message = "Select a business to export this report."

    def get(self, request):
        business = self._resolve_business(request)
        year = int(request.query_params.get("year") or timezone.now().year)
        month = request.query_params.get("month")

        if not business:
            return Response({"error": "No business found for this user"}, status=400)

        pdf_buffer = generate_report_pdf(
            business=business,
            year=year,
            month=int(month) if month else None,
        )

        filename = f"report-{year}{f'-{int(month):02d}' if month else ''}.pdf"
        return FileResponse(pdf_buffer, as_attachment=True, filename=filename)
