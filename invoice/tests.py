import os
from io import BytesIO
from decimal import Decimal

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image as PILImage

from business.models import Business
from users.models import User
from invoice.models import Invoice, InvoiceItem, Receipt
from invoice.utils import (
    generate_invoice_pdf,
    generate_receipt_pdf,
    _validate_logo_file,
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
        for template in ("classic", "modern", "minimal"):
            business = self._business(name=f"Template Business {template}")
            invoice = self._invoice(business, template=template)
            pdf_buffer = generate_invoice_pdf(invoice)
            self.assertTrue(pdf_buffer.getvalue().startswith(b"%PDF"))

    def test_pdf_supports_circular_logo_shape(self):
        business = self._business(name="Circle Logo Business", logo_shape="circle", logo=self._logo())
        invoice = self._invoice(business)
        pdf_buffer = generate_invoice_pdf(invoice)
        self.assertTrue(pdf_buffer.getvalue().startswith(b"%PDF"))