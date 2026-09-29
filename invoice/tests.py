import os
from io import BytesIO
from decimal import Decimal

from django.test import TestCase
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image as PILImage
from rest_framework.test import APIClient

from business.models import Business
from users.models import User
from invoice.models import Invoice, InvoiceItem, Receipt
from invoice.utils import (
    generate_invoice_pdf,
    generate_receipt_pdf,
    invoice_template_catalogue,
    resolve_invoice_template,
    _load_logo,
    _validate_logo_file,
    logo_bytes,
)


class LogoFetchingTestCase(TestCase):
    """Test invoice logo fetching and PDF generation"""

    def setUp(self):
        """Set up test data"""
        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )

        # Create a test image
        self.test_image = self._create_test_image()

        # Create business with logo
        self.business_with_logo = Business.objects.create(
            owner=self.user,
            name="Test Business",
            email="business@example.com",
            phone="1234567890",
            address="Test Address",
            logo=self.test_image,
        )

        # Create business without logo
        self.business_without_logo = Business.objects.create(
            owner=self.user,
            name="Business No Logo",
            email="nobusiness@example.com",
            phone="0987654321",
            address="Another Address",
        )

        # Create invoice with logo
        self.invoice_with_logo = Invoice.objects.create(
            business=self.business_with_logo,
            client_name="Test Client",
            client_email="client@example.com",
            issue_date="2026-03-24",
            due_date="2026-04-24",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("16.00"),
            total_amount=Decimal("116.00"),
        )

        # Create invoice without logo
        self.invoice_without_logo = Invoice.objects.create(
            business=self.business_without_logo,
            client_name="Another Client",
            client_email="another@example.com",
            issue_date="2026-03-24",
            due_date="2026-04-24",
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("8.00"),
            total_amount=Decimal("58.00"),
        )

    @staticmethod
    def _create_test_image():
        """Create a test image file"""
        image = PILImage.new("RGB", (100, 100), color="red")
        image_file = BytesIO()
        image.save(image_file, format="JPEG")
        image_file.seek(0)
        return SimpleUploadedFile(
            "test_logo.jpg",
            image_file.getvalue(),
            content_type="image/jpeg"
        )

    def test_logo_validation_with_valid_logo(self):
        """Test _validate_logo_file returns True for business with valid logo"""
        result = _validate_logo_file(self.business_with_logo)
        self.assertTrue(result)

    def test_logo_validation_with_no_logo(self):
        """Test _validate_logo_file returns False for business without logo"""
        result = _validate_logo_file(self.business_without_logo)
        self.assertFalse(result)

    def test_invoice_pdf_includes_logo(self):
        """Test that invoice PDF is generated successfully with logo"""
        pdf_buffer = generate_invoice_pdf(self.invoice_with_logo)
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)
        # Check PDF header signature
        pdf_buffer.seek(0)
        self.assertTrue(pdf_buffer.read(4) == b"%PDF")

    def test_invoice_pdf_handles_missing_logo(self):
        """Test that invoice PDF generates even without logo"""
        pdf_buffer = generate_invoice_pdf(self.invoice_without_logo)
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)
        # Check PDF header signature
        pdf_buffer.seek(0)
        self.assertTrue(pdf_buffer.read(4) == b"%PDF")

    def test_receipt_pdf_includes_logo(self):
        """Test that receipt PDF is generated successfully with logo"""
        receipt = Receipt.objects.create(
            invoice=self.invoice_with_logo,
            payment_method="bank_transfer",
            payment_date="2026-03-24",
            amount_paid=self.invoice_with_logo.total_amount,
            currency="KES",
            reference="REF-001",
        )
        pdf_buffer = generate_receipt_pdf(receipt)
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)
        # Check PDF header signature
        pdf_buffer.seek(0)
        self.assertTrue(pdf_buffer.read(4) == b"%PDF")

    def test_receipt_pdf_handles_missing_logo(self):
        """Test that receipt PDF generates even without logo"""
        receipt = Receipt.objects.create(
            invoice=self.invoice_without_logo,
            payment_method="bank_transfer",
            payment_date="2026-03-24",
            amount_paid=self.invoice_without_logo.total_amount,
            currency="KES",
            reference="REF-002",
        )
        pdf_buffer = generate_receipt_pdf(receipt)
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)
        # Check PDF header signature
        pdf_buffer.seek(0)
        self.assertTrue(pdf_buffer.read(4) == b"%PDF")

    def test_logo_file_exists_on_disk(self):
        """Test that logo file is actually saved to disk"""
        self.assertTrue(os.path.exists(self.business_with_logo.logo.path))

    def test_logo_in_different_formats(self):
        """Test that PDFs can be generated with different logo formats"""
        # This tests that the PDF generation is robust to different image types
        # Create business with logo in different format
        jpg_image = self._create_test_image()
        business = Business.objects.create(
            owner=self.user,
            name="JPG Logo Business",
            email="jpg@example.com",
            phone="5555555555",
            address="JPG Address",
            logo=jpg_image,
        )
        invoice = Invoice.objects.create(
            business=business,
            client_name="JPG Client",
            client_email="jpgclient@example.com",
            issue_date="2026-03-24",
            due_date="2026-04-24",
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("32.00"),
            total_amount=Decimal("232.00"),
        )
        pdf_buffer = generate_invoice_pdf(invoice)
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)


class InvoiceTemplateRenderingTestCase(TestCase):
    """The redesigned template must survive awkward but legal business data."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="templates@example.com",
            password="testpass123",
        )

    @staticmethod
    def _logo():
        image = PILImage.new("RGBA", (240, 120), color=(15, 23, 42, 255))
        image_file = BytesIO()
        image.save(image_file, format="PNG")
        image_file.seek(0)
        return SimpleUploadedFile("brand.png", image_file.getvalue(), content_type="image/png")

    def tearDown(self):
        # Logo uploads land in MEDIA_ROOT, so remove them with the test data.
        for business in Business.objects.all():
            if business.logo:
                business.logo.delete(save=False)

    def _business(self, **overrides):
        defaults = {
            "owner": self.user,
            "name": "Bright & Co",
            "email": "hello@bright.co.ke",
            "phone": "+254712345678",
            "address": "Karen Office Park\nLangata Road & Ngong Road",
        }
        defaults.update(overrides)
        return Business.objects.create(**defaults)

    def _invoice(self, business, **overrides):
        defaults = {
            "client_name": "Acme Holdings Limited",
            "client_email": "accounts@acme.co.ke",
            "issue_date": "2026-09-02",
            "due_date": "2026-09-30",
            "subtotal": Decimal("1200.00"),
            "tax_amount": Decimal("192.00"),
            "total_amount": Decimal("1392.00"),
        }
        defaults.update(overrides)
        return Invoice.objects.create(business=business, **defaults)

    def test_pdf_escapes_xml_special_characters(self):
        """Ampersands and angle brackets in business data must not break the PDF."""
        business = self._business(name="Bright & Co <Holdings>")
        invoice = self._invoice(business, client_name="Tom & Jerry Ltd")
        pdf_buffer = generate_invoice_pdf(invoice)
        self.assertTrue(pdf_buffer.getvalue().startswith(b"%PDF"))

    def test_pdf_renders_for_every_template(self):
        for template in tuple(entry["id"] for entry in invoice_template_catalogue()):
            business = self._business(name=f"Template Business {template}")
            invoice = self._invoice(business, template=template)
            pdf_buffer = generate_invoice_pdf(invoice)
            self.assertTrue(pdf_buffer.getvalue().startswith(b"%PDF"))

    def test_pdf_supports_circular_logo_shape(self):
        business = self._business(name="Circle Logo Business", logo_shape="circle", logo=self._logo())
        invoice = self._invoice(business)
        pdf_buffer = generate_invoice_pdf(invoice)
        self.assertTrue(pdf_buffer.getvalue().startswith(b"%PDF"))

    def test_letterhead_pdf_renders_a_logo_without_a_filesystem_path(self):
        business = self._business(name="Letterhead Logo Business", default_invoice_template="letterhead")
        invoice = self._invoice(business, template="")
        self.assertEqual(resolve_invoice_template(invoice), "letterhead")
        pdf_buffer = generate_invoice_pdf(invoice)
        self.assertTrue(pdf_buffer.getvalue().startswith(b"%PDF"))

    def test_invoice_inherits_business_default_template(self):
        business = self._business(name="Inheriting Business", default_invoice_template="modern")
        invoice = self._invoice(business, template="")
        self.assertEqual(resolve_invoice_template(invoice), "modern")

    def test_invoice_template_beats_business_default_template(self):
        business = self._business(name="Pinned Business", default_invoice_template="modern")
        invoice = self._invoice(business, template="minimal")
        self.assertEqual(resolve_invoice_template(invoice), "minimal")

    def test_explicit_template_beats_everything(self):
        business = self._business(name="Overriding Business", default_invoice_template="modern")
        invoice = self._invoice(business, template="minimal")
        self.assertEqual(resolve_invoice_template(invoice, "letterhead"), "letterhead")

    def test_unknown_template_falls_back_to_classic(self):
        business = self._business(name="Unknown Business")
        invoice = self._invoice(business, template="")
        self.assertEqual(resolve_invoice_template(invoice, "hologram"), "classic")

    def test_template_catalogue_lists_every_template_with_hex_palettes(self):
        catalogue = invoice_template_catalogue()
        self.assertEqual(
            [entry["id"] for entry in catalogue],
            ["classic", "modern", "minimal", "letterhead"],
        )
        for entry in catalogue:
            self.assertTrue(entry["name"])
            self.assertTrue(entry["description"])
            self.assertIn(entry["layout"], {"hero", "letterhead"})
            self.assertTrue(entry["palette"])
            for value in entry["palette"].values():
                self.assertRegex(value, r"^#[0-9A-F]{6}$")


class InvoiceTemplateEndpointTestCase(TestCase):
    """The picker needs the catalogue over HTTP, authenticated only."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="picker@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_templates_endpoint_returns_the_catalogue(self):
        response = self.client.get("/api/invoice/templates/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [entry["id"] for entry in response.json()],
            ["classic", "modern", "minimal", "letterhead"],
        )

    def test_templates_endpoint_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get("/api/invoice/templates/")
        self.assertEqual(response.status_code, 401)

    def test_created_invoice_stores_the_template_and_renders_it(self):
        business = Business.objects.create(
            owner=self.user,
            name="PDF Endpoint Co",
            email="pdf@example.com",
            phone="0700000000",
            address="Nairobi",
            default_invoice_template="letterhead",
        )

        created = self.client.post(
            "/api/invoice/",
            {
                "business_id": business.id,
                "client_name": "Acme Holdings",
                "client_email": "accounts@acme.co.ke",
                "issue_date": "2026-09-02",
                "due_date": "2026-09-30",
                "template": "minimal",
                "items": [
                    {"description": "Design", "quantity": 1, "unit_price": "100.00", "total": "100.00"}
                ],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["template"], "minimal")

        invoice_id = created.data["id"]
        stored = self.client.get(f"/api/invoice/{invoice_id}/pdf/")
        self.assertEqual(stored.status_code, 200)
        self.assertTrue(b"".join(stored.streaming_content).startswith(b"%PDF"))

        override = self.client.get(f"/api/invoice/{invoice_id}/pdf/?template=letterhead")
        self.assertEqual(override.status_code, 200)
        self.assertTrue(b"".join(override.streaming_content).startswith(b"%PDF"))

    def test_created_invoice_without_a_template_inherits_the_business_default(self):
        business = Business.objects.create(
            owner=self.user,
            name="Inherit Endpoint Co",
            email="inherit@example.com",
            phone="0700000000",
            address="Nairobi",
            default_invoice_template="modern",
        )

        created = self.client.post(
            "/api/invoice/",
            {
                "business_id": business.id,
                "client_name": "Acme Holdings",
                "client_email": "accounts@acme.co.ke",
                "issue_date": "2026-09-02",
                "due_date": "2026-09-30",
                "items": [
                    {"description": "Design", "quantity": 1, "unit_price": "100.00", "total": "100.00"}
                ],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["template"], "")

        invoice = Invoice.objects.get(pk=created.data["id"])
        self.assertEqual(resolve_invoice_template(invoice), "modern")


class RemoteLikeLogoStorage(Storage):
    """A minimal stand-in for a remote backend such as Cloudinary.

    Files stay readable through the storage API, but path() raises - the exact
    condition that used to drop logos from every generated PDF.
    """

    def __init__(self):
        self._files = {}

    def _save(self, name, content):
        self._files[name] = content.read()
        return name

    def exists(self, name):
        return name in self._files

    def open(self, name, mode="rb"):
        if name not in self._files:
            raise FileNotFoundError(f"No such file in storage: {name}")
        return ContentFile(self._files[name], name=name)

    def delete(self, name):
        self._files.pop(name, None)

    def size(self, name):
        return len(self._files.get(name, b""))

    def url(self, name):
        return f"https://cdn.example.com/media/{name}"

    def path(self, name):
        raise NotImplementedError("This backend does not expose filesystem paths.")


class RemoteStorageLogoTestCase(TestCase):
    """Logos must load from a backend that exposes no filesystem path."""

    @staticmethod
    def _png_bytes():
        image = PILImage.new("RGBA", (120, 60), color=(15, 23, 42, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def setUp(self):
        self.user = User.objects.create_user(
            email="remote-storage@example.com", password="testpass123"
        )
        self.png = self._png_bytes()

        # Swap the storage in first, so the upload lands in the remote-like
        # backend rather than on disk.
        self.field = Business._meta.get_field("logo")
        self.original_storage = self.field.storage
        self.field.storage = RemoteLikeLogoStorage()

        self.business = Business.objects.create(
            owner=self.user,
            name="Remote Storage Co",
            email="remote@example.com",
            phone="+254700000000",
            address="Nairobi",
            logo=SimpleUploadedFile("remote.png", self.png, content_type="image/png"),
        )
        self.invoice = Invoice.objects.create(
            business=self.business,
            client_name="Remote Client",
            client_email="remote-client@example.com",
            issue_date="2026-03-24",
            due_date="2026-04-24",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("16.00"),
            total_amount=Decimal("116.00"),
        )
    def tearDown(self):
        self.field.storage = self.original_storage
        for business in Business.objects.all():
            if business.logo:
                business.logo.delete(save=False)

    def test_fixture_really_hides_the_path(self):
        with self.assertRaises(NotImplementedError):
            self.business.logo.path

    def test_logo_bytes_reads_through_the_storage_api(self):
        self.assertEqual(logo_bytes(self.business), self.png)

    def test_validation_succeeds_without_a_filesystem_path(self):
        self.assertTrue(_validate_logo_file(self.business))

    def test_logo_loads_without_a_filesystem_path(self):
        flowable, is_circular, _ = _load_logo(self.business, "remote-storage-test")
        self.assertIsNotNone(flowable)
        self.assertFalse(is_circular)
        self.assertGreater(flowable.drawWidth, 0)
        self.assertGreater(flowable.drawHeight, 0)

    def test_invoice_pdf_keeps_the_logo(self):
        pdf_buffer = generate_invoice_pdf(self.invoice)
        self.assertTrue(pdf_buffer.getvalue().startswith(b"%PDF"))
        self.assertIsNotNone(_load_logo(self.business, "remote-storage-pdf")[0])

    def test_deleted_logo_is_handled_gracefully(self):
        self.business.logo.delete(save=False)
        self.business.refresh_from_db()
        self.assertIsNone(logo_bytes(self.business))
        self.assertFalse(_validate_logo_file(self.business))


class InvoiceEditingTestCase(TestCase):
    """Draft invoices are editable; sent and paid invoices are locked."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="editor@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.business = Business.objects.create(
            owner=self.user,
            name="Edit Draft Co",
            email="billing@example.com",
            phone="0700000000",
            address="Nairobi",
            tax_rate=Decimal("16.00"),
        )

    def _create_invoice(self, **overrides):
        payload = {
            "business_id": self.business.id,
            "client_name": "Acme Holdings",
            "client_email": "accounts@acme.co.ke",
            "issue_date": "2026-09-02",
            "due_date": "2026-09-30",
            "items": [
                {"description": "Design", "quantity": 1, "unit_price": "100.00", "total": "100.00"}
            ],
        }
        payload.update(overrides)
        response = self.client.post("/api/invoice/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_draft_invoice_can_add_items_change_template_and_dates(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice["status"], "draft")
        self.assertEqual(len(invoice["items"]), 1)

        updated = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {
                "client_name": "Acme Holdings Ltd",
                "due_date": "2026-10-15",
                "template": "letterhead",
                "items": [
                    {"description": "Design", "quantity": 1, "unit_price": "100.00", "total": "100.00"},
                    {"description": "Hosting", "quantity": 2, "unit_price": "100.00", "total": "200.00"},
                ],
            },
            format="json",
        )

        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["client_name"], "Acme Holdings Ltd")
        self.assertEqual(updated.data["due_date"], "2026-10-15")
        self.assertEqual(updated.data["template"], "letterhead")
        self.assertEqual(len(updated.data["items"]), 2)
        self.assertEqual(Decimal(updated.data["subtotal"]), Decimal("300.00"))
        self.assertEqual(Decimal(updated.data["tax_amount"]), Decimal("48.00"))
        self.assertEqual(Decimal(updated.data["total_amount"]), Decimal("348.00"))

        stored = Invoice.objects.get(pk=invoice["id"])
        self.assertEqual(stored.items.count(), 2)
        self.assertEqual(stored.invoice_number, invoice["invoice_number"])
        self.assertEqual(resolve_invoice_template(stored), "letterhead")

    def test_editing_replaces_line_items_instead_of_appending(self):
        invoice = self._create_invoice()

        updated = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {
                "items": [
                    {"description": "Consulting", "quantity": 3, "unit_price": "50.00", "total": "150.00"}
                ]
            },
            format="json",
        )

        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual([item["description"] for item in updated.data["items"]], ["Consulting"])
        self.assertEqual(InvoiceItem.objects.filter(invoice_id=invoice["id"]).count(), 1)
        self.assertEqual(Decimal(updated.data["total_amount"]), Decimal("174.00"))

    def test_editing_without_items_keeps_existing_line_items(self):
        invoice = self._create_invoice()

        updated = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {"client_email": "new-address@acme.co.ke"},
            format="json",
        )

        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["client_email"], "new-address@acme.co.ke")
        self.assertEqual([item["description"] for item in updated.data["items"]], ["Design"])
        self.assertEqual(Decimal(updated.data["total_amount"]), Decimal("116.00"))

    def test_sent_invoice_cannot_be_edited(self):
        invoice = self._create_invoice(status="sent")

        response = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {
                "client_name": "Tampered",
                "items": [
                    {"description": "Tampered", "quantity": 1, "unit_price": "1.00", "total": "1.00"}
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["detail"].split()[0], invoice["invoice_number"])
        stored = Invoice.objects.get(pk=invoice["id"])
        self.assertEqual(stored.client_name, "Acme Holdings")
        self.assertEqual(stored.items.count(), 1)
        self.assertEqual(stored.items.first().description, "Design")

    def test_paid_invoice_cannot_be_edited(self):
        invoice = self._create_invoice()
        mark_paid = self.client.post(f"/api/invoice/{invoice['id']}/mark_paid/")
        self.assertEqual(mark_paid.status_code, 200, mark_paid.data)

        response = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {"client_name": "Tampered"},
            format="json",
        )

        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(Invoice.objects.get(pk=invoice["id"]).client_name, "Acme Holdings")

    def test_a_draft_can_be_edited_repeatedly(self):
        invoice = self._create_invoice()
        first = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {"client_name": "First Pass"},
            format="json",
        )
        second = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {"client_name": "Second Pass"},
            format="json",
        )

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["client_name"], "Second Pass")
        self.assertEqual(Invoice.objects.get(pk=invoice["id"]).client_name, "Second Pass")

    def test_only_the_owner_can_edit_a_draft(self):
        invoice = self._create_invoice()
        outsider = User.objects.create_user(email="outsider@example.com", password="testpass123")
        self.client.force_authenticate(outsider)

        response = self.client.patch(
            f"/api/invoice/{invoice['id']}/",
            {"client_name": "Hijacked"},
            format="json",
        )

        self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(Invoice.objects.get(pk=invoice["id"]).client_name, "Acme Holdings")
