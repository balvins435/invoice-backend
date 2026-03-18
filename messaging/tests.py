from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from business.models import Business
from invoice.models import Invoice
from messaging.models import WhatsAppMessage
from payments.models import PaymentTransaction


class AutoPaidWhatsAppSignalTests(TestCase):
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
        self.client = APIClient()

    def _create_invoice(self):
        return Invoice.objects.create(
            business=self.business,
            invoice_number="INV-9001",
            client_name="Client A",
            client_email="client@example.com",
            issue_date=date.today(),
            due_date=date.today(),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("16.00"),
            total_amount=Decimal("116.00"),
            status="sent",
        )

    def test_auto_paid_whatsapp_sent_once_with_completed_payment_phone(self):
        invoice = self._create_invoice()
        PaymentTransaction.objects.create(
            business=self.business,
            invoice=invoice,
            phone_number="254712345678",
            amount=Decimal("116.00"),
            status=PaymentTransaction.STATUS_COMPLETED,
        )

        invoice.status = "paid"
        invoice.save(update_fields=["status"])

        message = WhatsAppMessage.objects.get(invoice=invoice)
        self.assertEqual(message.message_type, WhatsAppMessage.TYPE_AUTO_PAID)
        self.assertEqual(message.delivery_status, WhatsAppMessage.STATUS_SENT)
        self.assertEqual(message.idempotency_key, f"paid-invoice-{invoice.id}")
        self.assertEqual(message.phone_number, "254712345678")
        self.assertEqual(message.attempt_count, 1)

        # Re-saving paid invoice should not create duplicates.
        invoice.save(update_fields=["status"])
        self.assertEqual(WhatsAppMessage.objects.filter(invoice=invoice).count(), 1)

    def test_auto_paid_whatsapp_logs_failure_when_phone_missing(self):
        invoice = self._create_invoice()

        invoice.status = "paid"
        invoice.save(update_fields=["status"])

        message = WhatsAppMessage.objects.get(invoice=invoice)
        self.assertEqual(message.message_type, WhatsAppMessage.TYPE_AUTO_PAID)
        self.assertEqual(message.delivery_status, WhatsAppMessage.STATUS_FAILED)
        self.assertIn("no completed payment phone number", message.error_message.lower())
        self.assertEqual(message.attempt_count, 1)

    def test_manual_send_invoice_is_idempotent_with_header_key(self):
        self.client.force_authenticate(self.user)
        invoice = self._create_invoice()

        payload = {
            "invoice_id": invoice.id,
            "phone_number": "254712345678",
        }
        first = self.client.post(
            "/api/messaging/whatsapp/send-invoice/",
            payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY="wa-test-key-1",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(
            WhatsAppMessage.objects.filter(
                invoice=invoice,
                message_type=WhatsAppMessage.TYPE_MANUAL_INVOICE,
            ).count(),
            1,
        )

        second = self.client.post(
            "/api/messaging/whatsapp/send-invoice/",
            payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY="wa-test-key-1",
        )
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data.get("idempotent_replay"))
        self.assertEqual(
            WhatsAppMessage.objects.filter(
                invoice=invoice,
                message_type=WhatsAppMessage.TYPE_MANUAL_INVOICE,
            ).count(),
            1,
        )
