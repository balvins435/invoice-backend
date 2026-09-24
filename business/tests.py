import os
from io import BytesIO
from urllib.parse import urlparse

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from users.models import User

from .models import Business


def _logo_upload(name="test_logo_upload.png"):
    image = Image.new("RGB", (120, 60), color=(37, 99, 235))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class BusinessLogoUploadTests(TestCase):
    """A logo uploaded through the API must persist and stay downloadable."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="logo-owner@example.com",
            password="testpass123",
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Logo Upload Co",
            email="owner@example.com",
            phone="0700000000",
            address="Nairobi",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _upload(self, action="patch"):
        if action == "patch":
            return self.client.patch(
                f"/api/business/{self.business.id}/",
                {"business_name": "Logo Upload Co", "logo": _logo_upload()},
                format="multipart",
            )
        return self.client.post(
            "/api/business/",
            {
                "business_name": "Created With Logo",
                "email": "created@example.com",
                "logo": _logo_upload("test_logo_created.png"),
            },
            format="multipart",
        )

    def test_logo_upload_persists_on_the_business(self):
        response = self._upload()
        self.assertEqual(response.status_code, 200, response.data)
        self.business.refresh_from_db()
        self.assertTrue(self.business.logo)
        self.assertTrue(os.path.exists(self.business.logo.path))
        self.assertGreater(os.path.getsize(self.business.logo.path), 0)

    def test_logo_is_stored_when_creating_a_business(self):
        response = self._upload("post")
        self.assertEqual(response.status_code, 201, response.data)
        created = Business.objects.get(name="Created With Logo")
        self.assertTrue(created.logo)
        self.assertTrue(os.path.exists(created.logo.path))

    def test_returned_logo_url_is_downloadable(self):
        """Regression: outside DEBUG the media route was missing, so the URL 404'd."""
        response = self._upload()
        self.assertEqual(response.status_code, 200, response.data)
        download = self.client.get(urlparse(response.data["logo"]).path)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "image/png")
        body = b"".join(download.streaming_content)
        self.assertTrue(body.startswith(b"\x89PNG"))
