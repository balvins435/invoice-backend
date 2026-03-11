# Social authentication pipeline for Google and Microsoft OAuth.
from typing import Any, Dict, Optional

from .models import User


def create_user(
    backend: Any,
    details: Dict[str, Any],
    user: Optional[User] = None,
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    request = kwargs.get("request")
    if request:
        request.session["social_auth_last_login_backend"] = backend.name

    if user:
        if request:
            request.session["social_auth_is_new_user"] = False
        return {"is_new": False}

    email = (details.get("email") or "").strip().lower()
    if not email:
        if request:
            request.session["social_auth_is_new_user"] = False
        return {}

    full_name = (
        details.get("fullname")
        or details.get("full_name")
        or f"{details.get('first_name', '')} {details.get('last_name', '')}".strip()
    ).strip()

    if not full_name:
        full_name = email.split("@")[0]

    user = User.objects.create_user(email=email, full_name=full_name)
    if request:
        request.session["social_auth_is_new_user"] = True
    return {"user": user, "is_new": True}
