from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from business.models import Business
from invoice.models import Invoice, Receipt
from payments.models import PaymentTransaction
from payments.serializers import STKPushRequestSerializer


class MpesaIntegrationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="owner@example.com",
            password="pass1234",
            full_name="Owner User",
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Acme Ltd",
            email="biz@example.com",
            phone="+254700000000",
            address="Nairobi",
            tax_rate=Decimal("16.00"),
        )
        self.invoice = Invoice.objects.create(
            business=self.business,
            invoice_number="INV-0001",
            client_name="Client",
            client_email="client@example.com",
            issue_date=date.today(),
            due_date=date.today(),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("16.00"),
            total_amount=Decimal("116.00"),
            status="sent",
        )
        self.client = APIClient()

    def test_stk_serializer_normalizes_msisdn(self):
        serializer = STKPushRequestSerializer(
            data={
                "invoice_id": self.invoice.id,
                "phone_number": "0712345678",
                "amount": "100.00",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["phone_number"], "254712345678")

    def test_callback_marks_transaction_paid_and_is_idempotent(self):
        transaction = PaymentTransaction.objects.create(
            business=self.business,
            invoice=self.invoice,
            phone_number="254712345678",
            amount=Decimal("116.00"),
            checkout_request_id="ws_CO_123",
            merchant_request_id="ms_MR_123",
            status=PaymentTransaction.STATUS_PENDING,
        )

        payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_123",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 116.0},
                            {"Name": "MpesaReceiptNumber", "Value": "ABCD1234"},
                        ]
                    },
                }
            }
        }

        response = self.client.post("/api/payments/mpesa/callback/", payload, format="json")
        self.assertEqual(response.status_code, 200)

        transaction.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(transaction.status, PaymentTransaction.STATUS_COMPLETED)
        self.assertEqual(transaction.mpesa_receipt_number, "ABCD1234")
        self.assertEqual(self.invoice.status, "paid")
        self.assertEqual(Receipt.objects.filter(invoice=self.invoice).count(), 1)

        response_retry = self.client.post("/api/payments/mpesa/callback/", payload, format="json")
        self.assertEqual(response_retry.status_code, 200)
        self.assertEqual(Receipt.objects.filter(invoice=self.invoice).count(), 1)
