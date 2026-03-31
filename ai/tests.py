from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from business.models import Business
from users.models import User


class AIAssistantAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Acme Traders",
            email="acme@example.com",
            phone="+254700000001",
            address="Nairobi",
        )
        self.other_business = Business.objects.create(
            owner=self.other_user,
            name="Other Co",
            email="otherbiz@example.com",
            phone="+254700000002",
            address="Mombasa",
        )
        self.assistant_url = reverse("ai-assistant")
        self.invoice_url = reverse("ai-generate-invoice")

    def test_requires_authentication(self):
        response = self.client.post(self.assistant_url, {"prompt": "Draft an invoice"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("ai.views.generate_assistant_response")
    def test_assistant_returns_business_scoped_payload(self, mock_generate):
        self.client.force_authenticate(self.user)
        mock_generate.return_value = {
            "intent": "invoice",
            "reply": "Prepared a draft invoice.",
            "invoice_draft": {
                "client_name": "James",
                "client_email": "james@example.com",
                "issue_date": "2026-03-31",
                "due_date": "2026-04-30",
                "items": [{"description": "Consulting", "quantity": 1, "unit_price": 25000}],
            },
            "report_summary": None,
            "suggested_prompts": ["Send this by WhatsApp"],
        }

        response = self.client.post(
            self.assistant_url,
            {
                "prompt": "Create an invoice for James",
                "mode": "invoice",
                "business_id": self.business.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["intent"], "invoice")
        mock_generate.assert_called_once()
        self.assertEqual(mock_generate.call_args.kwargs["business"], self.business)

    def test_rejects_foreign_business(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            self.assistant_url,
            {
                "prompt": "Summarize this business",
                "mode": "report",
                "business_id": self.other_business.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("business_id", response.data)

    @patch("ai.views.generate_invoice_from_text")
    def test_generate_invoice_endpoint_returns_draft(self, mock_generate_invoice):
        self.client.force_authenticate(self.user)
        mock_generate_invoice.return_value = {
            "client_name": "James",
            "client_email": "james@example.com",
            "issue_date": "2026-03-31",
            "due_date": "2026-04-30",
            "items": [{"description": "Design work", "quantity": 2, "unit_price": 15000}],
        }

        response = self.client.post(
            self.invoice_url,
            {"text": "Invoice James for two design sessions"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["client_name"], "James")
