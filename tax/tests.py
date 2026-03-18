from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from business.models import Business
from invoice.models import Invoice
from tax.models import TaxSubmission


class TaxSubmissionIdempotencyTests(TestCase):
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
        self.client.force_authenticate(self.user)

    def test_submit_invoice_is_idempotent_with_header_key(self):
        payload = {"invoice_id": self.invoice.id}
        first = self.client.post(
            "/api/tax/submissions/submit-invoice/",
            payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY="tax-test-key-1",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(TaxSubmission.objects.count(), 1)

        second = self.client.post(
            "/api/tax/submissions/submit-invoice/",
            payload,
            format="json",
            HTTP_X_IDEMPOTENCY_KEY="tax-test-key-1",
        )
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data.get("idempotent_replay"))
        self.assertEqual(TaxSubmission.objects.count(), 1)
