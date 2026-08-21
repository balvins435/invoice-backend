import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from users.models import User

logger = logging.getLogger(__name__)


def change_password(*, user, current_password, new_password):
    if not user.check_password(current_password):
        return False
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return True


def request_password_reset(email):
    user = User.objects.filter(email=email, is_active=True).first()
    if not user:
        return
    token = PasswordResetTokenGenerator().make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    message = f"We received a request to reset your password.\n\nReset your password using this link:\n{reset_link}\n\nIf you did not request this, you can safely ignore this email."
    try:
        send_mail("Reset your SmartInvoice password", message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception as exc:
        logger.exception("Password reset email failed for %s: %s", email, exc)


def confirm_password_reset(*, uid, token, new_password):
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except (User.DoesNotExist, ValueError, TypeError):
        return "invalid"
    if not PasswordResetTokenGenerator().check_token(user, token):
        return "expired"
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return "ok"
