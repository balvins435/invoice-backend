import base64
import json
import smtplib
from decimal import Decimal
from unittest import mock
from io import BytesIO
from urllib import error as urlerror

from django.core import mail
from django.core.mail.backends.smtp import EmailBackend
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from business.models import Business
from invoice.email_utils import (
    SENDGRID_PROVIDER,
    SMTP_PROVIDER,
    EmailConfigurationError,
    InvoiceEmailError,
    email_diagnostics,
    probe_email_provider,
    resolve_provider,
    send_email_message,
    send_invoice_email,
    validate_email_configuration,
)
from invoice.models import Invoice
from users.models import User


SENDGRID_SETTINGS = dict(
    EMAIL_PROVIDER=SENDGRID_PROVIDER,
    SENDGRID_API_KEY="SG.test-key",
    SENDGRID_FROM_EMAIL="billing@example.com",
)

SMTP_SETTINGS = dict(
    EMAIL_PROVIDER=SMTP_PROVIDER,
    EMAIL_HOST="smtp.example.com",
    EMAIL_PORT=587,
    EMAIL_HOST_USER="billing@example.com",
    EMAIL_HOST_PASSWORD="app-password",
    DEFAULT_FROM_EMAIL="billing@example.com",
)

SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

UNCONFIGURED_SETTINGS = dict(
    EMAIL_PROVIDER="",
    SENDGRID_API_KEY="",
    SENDGRID_FROM_EMAIL="",
    DEFAULT_FROM_EMAIL="",
    EMAIL_HOST="",
    EMAIL_HOST_USER="",
    EMAIL_HOST_PASSWORD="",
)


class FakeResponse:
    def __init__(self, status=202, body=b""):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class ProviderSelectionTests(TestCase):
    @override_settings(EMAIL_PROVIDER="", SENDGRID_API_KEY="")
    def test_defaults_to_smtp_without_sendgrid_key(self):
        self.assertEqual(resolve_provider(), SMTP_PROVIDER)

    @override_settings(EMAIL_PROVIDER="", SENDGRID_API_KEY="SG.key")
    def test_auto_selects_sendgrid_when_key_is_present(self):
        self.assertEqual(resolve_provider(), SENDGRID_PROVIDER)

    @override_settings(EMAIL_PROVIDER="smtp", SENDGRID_API_KEY="SG.key")
    def test_explicit_provider_wins_over_credentials(self):
        self.assertEqual(resolve_provider(), SMTP_PROVIDER)

    @override_settings(EMAIL_PROVIDER="postmark")
    def test_rejects_unknown_provider(self):
        with self.assertRaisesMessage(EmailConfigurationError, "not supported"):
            resolve_provider()


class ConfigurationValidationTests(TestCase):
    @override_settings(**SENDGRID_SETTINGS)
    def test_sendgrid_configuration_is_valid(self):
        self.assertEqual(validate_email_configuration(), SENDGRID_PROVIDER)

    @override_settings(EMAIL_PROVIDER=SENDGRID_PROVIDER, SENDGRID_API_KEY="", SENDGRID_FROM_EMAIL="a@b.com")
    def test_sendgrid_without_api_key_is_rejected(self):
        with self.assertRaisesMessage(EmailConfigurationError, "SENDGRID_API_KEY is not set"):
            validate_email_configuration()

    @override_settings(EMAIL_PROVIDER=SENDGRID_PROVIDER, SENDGRID_API_KEY="SG.key", SENDGRID_FROM_EMAIL="", DEFAULT_FROM_EMAIL="")
    def test_sendgrid_without_sender_is_rejected(self):
        with self.assertRaisesMessage(EmailConfigurationError, "SENDGRID_FROM_EMAIL"):
            validate_email_configuration()

    @override_settings(**UNCONFIGURED_SETTINGS)
    def test_smtp_without_credentials_is_rejected_with_guidance(self):
        with self.assertRaises(EmailConfigurationError) as ctx:
            validate_email_configuration()
        message = str(ctx.exception)
        self.assertIn("EMAIL_HOST_USER", message)
        self.assertIn("EMAIL_HOST_PASSWORD", message)
        self.assertIn("SENDGRID_API_KEY", message)

    @override_settings(**{**UNCONFIGURED_SETTINGS, "IS_RENDER": True})
    def test_render_deployment_is_warned_about_blocked_smtp_ports(self):
        with self.assertRaises(EmailConfigurationError) as ctx:
            validate_email_configuration()
        self.assertIn("ports 25, 465 and 587", str(ctx.exception))


class EmailDeliveryTests(TestCase):
    @override_settings(**{**SENDGRID_SETTINGS, "EMAIL_TIMEOUT": 5})
    def test_send_email_message_uses_sendgrid_http_api(self):
        with mock.patch("invoice.email_utils.urlrequest.urlopen", return_value=FakeResponse()) as urlopen:
            send_email_message(subject="Hello", recipients=["client@example.com"], text_content="Body")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.sendgrid.com/v3/mail/send")
        self.assertEqual(request.get_header("Authorization"), "Bearer SG.test-key")

    @override_settings(**SENDGRID_SETTINGS)
    def test_sendgrid_http_error_is_reported(self):
        error = urlerror.HTTPError(
            "https://api.sendgrid.com/v3/mail/send",
            403,
            "Forbidden",
            {},
            BytesIO(b'{"errors": [{"message": "sender not verified"}]}'),
        )
        with mock.patch("invoice.email_utils.urlrequest.urlopen", side_effect=error):
            with self.assertRaisesMessage(InvoiceEmailError, "SendGrid rejected the message (403)"):
                send_email_message(subject="Hello", recipients=["client@example.com"], text_content="Body")

    @override_settings(**{**SMTP_SETTINGS, "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"})
    def test_send_email_message_uses_smtp_backend(self):
        send_email_message(subject="Hello", recipients=["client@example.com"], text_content="Body")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["client@example.com"])

    @override_settings(**{**SMTP_SETTINGS, "EMAIL_BACKEND": SMTP_BACKEND})
    def test_smtp_authentication_error_explains_app_password(self):
        auth_error = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        with mock.patch.object(EmailBackend, "send_messages", side_effect=auth_error):
            with self.assertRaisesMessage(InvoiceEmailError, "SMTP authentication failed"):
                send_email_message(subject="Hello", recipients=["client@example.com"], text_content="Body")

    @override_settings(**{**SMTP_SETTINGS, "EMAIL_BACKEND": SMTP_BACKEND})
    def test_smtp_connection_error_mentions_blocked_ports(self):
        with mock.patch.object(EmailBackend, "send_messages", side_effect=OSError("connection refused")):
            with self.assertRaisesMessage(InvoiceEmailError, "Could not reach the SMTP server"):
                send_email_message(subject="Hello", recipients=["client@example.com"], text_content="Body")

    @override_settings(**{**SMTP_SETTINGS, "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"})
    def test_missing_recipient_is_rejected(self):
        with self.assertRaisesMessage(EmailConfigurationError, "No recipient address"):
            send_email_message(subject="Hello", recipients=[], text_content="Body")


class EmailDiagnosticsTests(TestCase):
    @override_settings(**{**UNCONFIGURED_SETTINGS, "IS_RENDER": True})
    def test_reports_unconfigured_deployment(self):
        report = email_diagnostics()

        self.assertFalse(report["ready"])
        self.assertTrue(report["on_render"])
        self.assertTrue(report["problems"])
        self.assertIn("SENDGRID_API_KEY", " ".join(report["problems"]))
        self.assertNotIn("SG.", str(report))

    @override_settings(**SENDGRID_SETTINGS)
    def test_probe_checks_sendgrid_api_key(self):
        with mock.patch("invoice.email_utils.urlrequest.urlopen", return_value=FakeResponse(status=200)):
            report = probe_email_provider()

        self.assertTrue(report["ok"])

    @override_settings(**SENDGRID_SETTINGS)
    def test_probe_reports_rejected_api_key(self):
        error = urlerror.HTTPError(
            "https://api.sendgrid.com/v3/scopes", 401, "Unauthorized", {}, BytesIO(b"{}")
        )
        with mock.patch("invoice.email_utils.urlrequest.urlopen", side_effect=error):
            report = probe_email_provider()

        self.assertFalse(report["ok"])
        self.assertIn("401", report["detail"])

    @override_settings(**{**SMTP_SETTINGS, "IS_RENDER": True})
    def test_render_smtp_advisory_is_a_warning_not_a_blocker(self):
        report = email_diagnostics()

        self.assertTrue(report["ready"])
        self.assertEqual(report["problems"], [])
        self.assertIn("ports 25, 465 and 587", " ".join(report["warnings"]))

    @override_settings(**SENDGRID_SETTINGS)
    def test_does_not_leak_secrets(self):
        report = email_diagnostics(probe=False)

        self.assertTrue(report["sendgrid_api_key_configured"])
        self.assertNotIn("test-key", str(report))


@override_settings(SECURE_SSL_REDIRECT=False)
def create_invoice_fixture():
    """Create an owner, a business and a draft invoice."""
    user = User.objects.create_user(email="owner@example.com", password="testpass123")
    business = Business.objects.create(
        owner=user,
        name="Test Business",
        email="business@example.com",
        phone="0700000000",
        address="Nairobi",
    )
    invoice = Invoice.objects.create(
        business=business,
        invoice_number="INV-0001",
        client_name="Test Client",
        client_email="client@example.com",
        issue_date="2026-09-23",
        due_date="2026-10-23",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("16.00"),
        total_amount=Decimal("116.00"),
        status="draft",
    )
    return user, business, invoice


class InvoiceEmailEndpointTests(TestCase):
    def setUp(self):
        self.user, self.business, self.invoice = create_invoice_fixture()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = f"/api/invoice/{self.invoice.pk}/send_email/"

    def test_successful_send_marks_invoice_as_sent(self):
        with mock.patch("invoice.application.services.send_invoice_email"):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "sent")

    @override_settings(**{**UNCONFIGURED_SETTINGS, "IS_RENDER": True})
    def test_unconfigured_email_returns_actionable_503(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "email_not_configured")
        self.assertIn("EMAIL_HOST_USER", response.data["error"])
        self.assertIn("ports 25, 465 and 587", response.data["error"])

    def test_delivery_failure_returns_502_with_reason(self):
        with mock.patch(
            "invoice.application.services.send_invoice_email",
            side_effect=InvoiceEmailError("SendGrid rejected the message (403): sender not verified"),
        ):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "email_delivery_failed")
        self.assertIn("sender not verified", response.data["error"])

    def test_email_diagnostics_endpoint_reports_configuration(self):
        with override_settings(**UNCONFIGURED_SETTINGS):
            response = self.client.get("/api/invoice/email-diagnostics/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("ready", response.data)
        self.assertFalse(response.data["ready"])

    def test_email_diagnostics_never_returns_credentials(self):
        with override_settings(**SENDGRID_SETTINGS):
            response = self.client.get("/api/invoice/email-diagnostics/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ready"])
        self.assertEqual(response.data["provider"], SENDGRID_PROVIDER)
        self.assertNotIn("test-key", str(response.data))


class InvoiceEmailContentTests(TestCase):
    def setUp(self):
        self.user, self.business, self.invoice = create_invoice_fixture()

    @override_settings(**{**SMTP_SETTINGS, "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"})
    def test_invoice_email_attaches_the_pdf(self):
        send_invoice_email(self.invoice)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["client@example.com"])
        self.assertIn("INV-0001", message.subject)
        self.assertEqual(len(message.attachments), 1)
        filename, content, mimetype = message.attachments[0]
        self.assertEqual(filename, "INV-0001.pdf")
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF"))

@override_settings(SECURE_SSL_REDIRECT=False)
class InvoiceEmailDeliveryIntegrationTests(TestCase):
    """Request -> view -> service -> provider chain with a stubbed SendGrid API."""

    def setUp(self):
        self.user, self.business, self.invoice = create_invoice_fixture()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = f"/api/invoice/{self.invoice.pk}/send_email/"

    @override_settings(**SENDGRID_SETTINGS)
    def test_invoice_is_delivered_and_marked_as_sent(self):
        with mock.patch(
            "invoice.email_utils.urlrequest.urlopen", return_value=FakeResponse(status=202)
        ) as urlopen:
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "sent")

        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["personalizations"][0]["to"], [{"email": "client@example.com"}])
        self.assertEqual(payload["from"], {"email": "billing@example.com"})
        self.assertIn("INV-0001", payload["personalizations"][0]["subject"])

        attachment = payload["attachments"][0]
        self.assertEqual(attachment["filename"], "INV-0001.pdf")
        self.assertEqual(attachment["type"], "application/pdf")
        self.assertEqual(attachment["disposition"], "attachment")
        self.assertTrue(base64.b64decode(attachment["content"]).startswith(b"%PDF"))

    @override_settings(**{**SENDGRID_SETTINGS, "EMAIL_PROVIDER": ""})
    def test_unset_provider_uses_sendgrid_credentials(self):
        with mock.patch(
            "invoice.email_utils.urlrequest.urlopen", return_value=FakeResponse(status=202)
        ):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "sent")
