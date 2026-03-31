from django.urls import path
from .views import AIAssistantAPIView, GenerateInvoiceAPIView

urlpatterns = [
    path("assistant/", AIAssistantAPIView.as_view(), name="ai-assistant"),
    path("generate-invoice/", GenerateInvoiceAPIView.as_view(), name="ai-generate-invoice"),
]
