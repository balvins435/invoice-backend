from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from business.models import Business
from .services import monthly_report, monthly_reports_for_year, tax_summary
from invoice.models import Invoice
from expenses.models import Expense
from django.db.models import Sum


class MonthlyReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _resolve_business(self, request):
        business_id = request.query_params.get('business') or request.query_params.get('business_id')
        queryset = Business.objects.filter(owner=request.user)
        if business_id:
            return queryset.filter(id=business_id).first()
        return queryset.order_by('id').first()

    def get(self, request):
        business = self._resolve_business(request)
        month = request.query_params.get('month')
        year = int(request.query_params.get('year') or datetime.utcnow().year)

        if not business:
            return Response(
                {"error": "No business found for this user"},
                status=400
            )

        if month:
            report = monthly_report(
                business=business,
                month=int(month),
                year=year
            )
            return Response(report)

        report = monthly_reports_for_year(business=business, year=year)
        return Response(report)


class TaxSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _resolve_business(self, request):
        business_id = request.query_params.get('business') or request.query_params.get('business_id')
        queryset = Business.objects.filter(owner=request.user)
        if business_id:
            return queryset.filter(id=business_id).first()
        return queryset.order_by('id').first()

    def get(self, request):
        business = self._resolve_business(request)
        year = int(request.query_params.get('year') or datetime.utcnow().year)
        month = request.query_params.get('month')

        if not business:
            return Response({"error": "No business found for this user"}, status=400)

        return Response(tax_summary(
            business=business,
            year=year,
            month=int(month) if month else None
        ))


class DashboardStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        business = Business.objects.filter(owner=request.user).order_by('id').first()
        if not business:
            return Response(
                {
                    "total_income": 0,
                    "total_expenses": 0,
                    "net_profit": 0,
                    "pending_invoices": 0,
                    "overdue_invoices": 0,
                    "recent_invoices": [],
                    "recent_expenses": [],
                    "monthly_trends": [],
                }
            )

        income_invoices = Invoice.objects.filter(business=business, status__in=['sent', 'paid'])
        all_invoices = Invoice.objects.filter(business=business)
        expenses = Expense.objects.filter(business=business)

        total_income = income_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
        total_expenses = expenses.aggregate(total=Sum('total_amount'))['total'] or 0

        return Response(
            {
                "total_income": float(total_income),
                "total_expenses": float(total_expenses),
                "net_profit": float(total_income - total_expenses),
                "pending_invoices": all_invoices.filter(status='sent').count(),
                "overdue_invoices": 0,
                "recent_invoices": [],
                "recent_expenses": [],
                "monthly_trends": [],
            }
        )
