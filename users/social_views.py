# Social authentication views for Google and Microsoft OAuth.
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken


def _callback_url() -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/social-callback"


class SocialAuthRedirectView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            params = urlencode({"error": "unauthorized"})
            return redirect(f"{_callback_url()}?{params}")

        refresh = RefreshToken.for_user(request.user)
        provider = request.session.get("social_auth_last_login_backend", "")
        params = urlencode(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "provider": provider,
            }
        )
        request.session.pop("social_auth_last_login_backend", None)
        return redirect(f"{_callback_url()}?{params}")


class SocialAuthErrorView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        error = request.GET.get("error") or request.GET.get("message") or "oauth_failed"
        params = urlencode({"error": error})
        return redirect(f"{_callback_url()}?{params}")
