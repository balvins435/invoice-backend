# Social authentication views for Google and Microsoft OAuth.
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from rest_framework import permissions
from rest_framework.response import Response
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
        is_new = request.session.get("social_auth_is_new_user", False)
        params = urlencode(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "provider": provider,
                "is_new": "1" if is_new else "0",
            }
        )
        request.session.pop("social_auth_last_login_backend", None)
        request.session.pop("social_auth_is_new_user", None)
        return redirect(f"{_callback_url()}?{params}")


class SocialAuthErrorView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        error = request.GET.get("error") or request.GET.get("message") or "oauth_failed"
        params = urlencode({"error": error})
        return redirect(f"{_callback_url()}?{params}")


class SocialProvidersView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        providers = []

        if settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY and settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET:
            providers.append(
                {
                    "id": "google",
                    "label": "Google",
                    "slug": "google-oauth2",
                }
            )

        if settings.SOCIAL_AUTH_AZUREAD_OAUTH2_KEY and settings.SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET:
            providers.append(
                {
                    "id": "microsoft",
                    "label": "Microsoft",
                    "slug": "azuread-oauth2",
                }
            )

        base_url = settings.BACKEND_BASE_URL.rstrip("/")
        for provider in providers:
            provider["login_url"] = f"{base_url}/api/oauth/login/{provider['slug']}/"

        return Response({"providers": providers})
