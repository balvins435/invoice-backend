from django.urls import path
from .views import MonthlyReportAPIView, TaxSummaryAPIView, DashboardStatsAPIView, ReportPDFAPIView

urlpatterns = [
    path('monthly/', MonthlyReportAPIView.as_view()),
    path('tax-summary/', TaxSummaryAPIView.as_view()),
    path('dashboard-stats/', DashboardStatsAPIView.as_view()),
    path('pdf/', ReportPDFAPIView.as_view()),
]
