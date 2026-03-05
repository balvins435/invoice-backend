from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MpesaCallbackAPIView, PaymentTransactionViewSet

router = DefaultRouter()
router.register("transactions", PaymentTransactionViewSet, basename="payment-transactions")

urlpatterns = [
    path("mpesa/callback/", MpesaCallbackAPIView.as_view(), name="mpesa-callback"),
    *router.urls,
]
