from django.urls import path
from .views import MonthlyReportAPIView

urlpatterns = [
    path('reports/monthly/', MonthlyReportAPIView.as_view()),
]
