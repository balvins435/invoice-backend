from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PublicInvoicePDFView, WhatsAppMessageViewSet

router = DefaultRouter()
router.register("whatsapp", WhatsAppMessageViewSet, basename="whatsapp-messages")

urlpatterns = [
    path("invoice-link/<str:token>/", PublicInvoicePDFView.as_view(), name="messaging-public-invoice-pdf"),
    *router.urls,
]
