"""Email delivery adapters shared by every outbound app email.

Three providers are supported:

* ``sendgrid`` - HTTP API, required on hosts that block outbound SMTP.
* ``brevo``    - HTTP API, the alternative when a SendGrid account cannot send.
* ``smtp``     - classic SMTP relay, the default for local development.

``settings.EMAIL_PROVIDER`` selects the provider explicitly. When it is left
blank the provider is auto-selected: the first HTTP provider holding an API key
in ``settings.HTTP_PROVIDERS`` order, SMTP otherwise.

Values for the provider come from environment variables, which are frequently
pasted into dashboard textareas. They are sanitised on read (surrounding
whitespace, newlines and wrapping quotes are removed) because a trailing newline
in SENDGRID_API_KEY or SENDGRID_FROM_EMAIL makes SendGrid reject the request
with 401/403.

Render's free instance type blocks outbound traffic on ports 25, 465 and 587,
so SMTP delivery cannot work there regardless of the credentials used. An HTTP
provider (or a paid instance type) is required in that case.
"""
import base64
import json
import logging
import os
import smtplib
from socket import timeout as socket_timeout
from urllib import error as urlerror
from urllib import request as urlrequest

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from .utils import generate_invoice_pdf

logger = logging.getLogger(__name__)

SMTP_PROVIDER = "smtp"
BREVO_PROVIDER = "brevo"
SENDGRID_PROVIDER = "sendgrid"

# Settings and display name per HTTP provider. Insertion order is also the
# auto-selection precedence used when EMAIL_PROVIDER is left empty, so SendGrid
# keeps winning for deployments that already hold its key.
HTTP_PROVIDERS = {
    SENDGRID_PROVIDER: {
        "api_key": "SENDGRID_API_KEY",
        "from_email": "SENDGRID_FROM_EMAIL",
        "label": "SendGrid",
    },
    BREVO_PROVIDER: {
        "api_key": "BREVO_API_KEY",
        "from_email": "BREVO_FROM_EMAIL",
        "label": "Brevo",
    },
}

SUPPORTED_PROVIDERS = (SMTP_PROVIDER,) + tuple(HTTP_PROVIDERS)

SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"
SENDGRID_SCOPES_URL = "https://api.sendgrid.com/v3/scopes"
SENDGRID_CREDITS_URL = "https://api.sendgrid.com/v3/user/credits"

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_ACCOUNT_URL = "https://api.brevo.com/v3/account"
BREVO_KEY_PREFIX = "xkeysib-"

SMTP_EGRESS_BLOCKED_HINT = (
    "Render blocks outbound SMTP traffic on ports 25, 465 and 587 for free web "
    "services, so SMTP delivery cannot work there. Configure an HTTP email API "
    "instead (SENDGRID_API_KEY or BREVO_API_KEY, each with its own "
    "<PROVIDER>_FROM_EMAIL) or move the service to a paid instance type."
)

SMTP_AUTH_HINT = (
    "Gmail requires a 16 character app password from "
    "https://myaccount.google.com/apppasswords with 2-step verification enabled; "
    "the account password is always rejected."
)

# Consumer mailboxes cannot be authenticated as a sending domain, so SendGrid only
# accepts them after the exact address is added as a verified Single Sender.
FREEMAIL_DOMAINS = (
    "aol.com",
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
)


class InvoiceEmailError(Exception):
    """Raised when an email could not be delivered."""


class EmailConfigurationError(InvoiceEmailError):
    """Raised when the active email provider is missing required configuration."""


def _clean(value):
    """Strip stray whitespace, newlines and wrapping quotes from an env value."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return text


def _setting(name, default=""):
    value = _clean(getattr(settings, name, None))
    if value is None or value == "":
        return default
    return value


def _is_render():
    return bool(getattr(settings, "IS_RENDER", False))


def _timeout():
    return getattr(settings, "EMAIL_TIMEOUT", None) or 10


def _smtp_endpoint():
    return f"{_setting('EMAIL_HOST', 'the configured SMTP host')}:{getattr(settings, 'EMAIL_PORT', '')}"


def _smtp_settings_error(exc):
    return (
        f"SMTP settings are invalid: {exc} Check EMAIL_PORT, EMAIL_USE_TLS and "
        "EMAIL_USE_SSL; at most one of TLS and SSL may be enabled."
    )


def _smtp_unreachable_error(exc):
    message = f"Could not reach the SMTP server at {_smtp_endpoint()} ({exc})."
    if _is_render():
        message = f"{message} {SMTP_EGRESS_BLOCKED_HINT}"
    return message


def _provider_api_key(provider):
    return _setting(HTTP_PROVIDERS[provider]["api_key"])


def _provider_sender(provider):
    """From address for an HTTP provider, falling back to the shared default."""
    for name in (HTTP_PROVIDERS[provider]["from_email"], "DEFAULT_FROM_EMAIL"):
        value = _setting(name)
        if value:
            return value
    return ""


def configured_http_providers():
    """HTTP providers holding an API key, in auto-selection order."""
    return [name for name in HTTP_PROVIDERS if _provider_api_key(name)]


def _sender_for(provider):
    """From address for the active transport."""
    if provider in HTTP_PROVIDERS:
        return _provider_sender(provider)
    return _setting("DEFAULT_FROM_EMAIL") or _setting("EMAIL_HOST_USER")


def resolve_provider():
    """Return the provider to use: ``sendgrid``, ``brevo`` or ``smtp``."""
    configured = str(_setting("EMAIL_PROVIDER")).strip().lower()
    if configured:
        if configured not in SUPPORTED_PROVIDERS:
            raise EmailConfigurationError(
                f"EMAIL_PROVIDER='{configured}' is not supported. "
                "Use one of: "
                + ", ".join(SUPPORTED_PROVIDERS)
                + "."
            )
        return configured
    available = configured_http_providers()
    return available[0] if available else SMTP_PROVIDER


def validate_email_configuration():
    """Return the active provider, raising when it cannot be used to send mail."""
    provider = resolve_provider()

    if provider in HTTP_PROVIDERS:
        names = HTTP_PROVIDERS[provider]
        if not _provider_api_key(provider):
            message = (
                f"EMAIL_PROVIDER is '{provider}' but {names['api_key']} is not set. "
                f"Add the {names['label']} API key, or set EMAIL_PROVIDER to one of: "
                + ", ".join(SUPPORTED_PROVIDERS)
                + "."
            )
            # Naming a provider whose key is absent is the usual mistake when moving
            # between providers, so point at whichever one is actually ready to send.
            others = [name for name in configured_http_providers() if name != provider]
            if others:
                message += (
                    f" {HTTP_PROVIDERS[others[0]]['label']} already has a key configured,"
                    f" so EMAIL_PROVIDER={others[0]} would use it."
                )
            raise EmailConfigurationError(message)
        if not _provider_sender(provider):
            raise EmailConfigurationError(
                f"Set {names['from_email']} to a sender verified with "
                f"{names['label']} (or set DEFAULT_FROM_EMAIL) so outbound email has "
                "a valid From address."
            )
        return provider

    missing = [
        name
        for name in ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD")
        if not _setting(name)
    ]
    if missing:
        verbs = "is" if len(missing) == 1 else "are"
        message = f"SMTP email delivery is selected but {' and '.join(missing)} {verbs} not set."
        if not str(_setting("EMAIL_PROVIDER")).strip():
            message += (
                " EMAIL_PROVIDER is not set and no HTTP provider key is configured, so "
                "SMTP is used by default; configure SENDGRID_API_KEY or BREVO_API_KEY "
                "for HTTP delivery."
            )
        if _is_render():
            message = f"{message} {SMTP_EGRESS_BLOCKED_HINT}"
        raise EmailConfigurationError(message)

    return provider


def _build_invoice_email_content(invoice):
    context = {
        "invoice": invoice,
        "business": invoice.business,
    }
    subject = f"Invoice {invoice.invoice_number} from {invoice.business.name}"
    text_content = render_to_string("emails/invoice_email.txt", context)
    html_content = render_to_string("emails/invoice_email.html", context)
    return subject, text_content, html_content


def _normalise_attachments(attachments):
    return [
        (filename, content if isinstance(content, bytes) else bytes(content), mimetype or "application/octet-stream")
        for filename, content, mimetype in attachments
    ]


SENDGRID_HINTS = (
    (
        ("verified sender", "sender identity", "does not match a verified"),
        "SENDGRID_FROM_EMAIL must be an address verified in SendGrid "
        "(Settings -> Sender Authentication -> Single Sender Verification), or a "
        "domain you have authenticated there.",
    ),
    (
        ("credits", "quota", "plan limit", "suspended", "billing"),
        "The SendGrid account cannot send right now (credits, plan limit or "
        "suspension). Check the account status in the SendGrid dashboard.",
    ),
)


def _summarise_provider_detail(body):
    """Reduce a provider error envelope to the sentence the provider wrote.

    SendGrid answers with {"errors": [{"message": ...}]} and Brevo with
    {"message": ..., "code": ...}; showing either envelope verbatim in a toast
    buries the one sentence that matters.
    """
    raw = (body or "").strip()
    if not raw:
        return "empty response body"
    try:
        payload = json.loads(raw)
    except ValueError:
        return raw
    if not isinstance(payload, dict):
        return raw
    messages = [
        entry["message"]
        for entry in (payload.get("errors") or [])
        if isinstance(entry, dict) and entry.get("message")
    ]
    if not messages and payload.get("message"):
        messages = [payload["message"]]
    return "; ".join(messages) if messages else raw


BREVO_KEY_HINT = (
    "BREVO_API_KEY was rejected: check the key is current, copied without stray "
    "whitespace, and starts with xkeysib-."
)

BREVO_HINTS = (
    (
        ("unrecognised ip", "unrecognized ip", "authorised ip", "authorized ip",
         "authorised_ips", "authorized_ips"),
        "Brevo is refusing this deployment outbound IP, not the API key. Remove the "
        "restriction at https://app.brevo.com/security/authorised_ips, or allowlist "
        "every outbound IP range of the Render service (Dashboard -> the service -> "
        "Connect -> Outbound). Render shares those ranges with other services, so a "
        "single address can stop working.",
    ),
    (
        ("sender", "from address", "not valid", "not verified", "not authorised",
         "not authorized"),
        "BREVO_FROM_EMAIL must be a sender verified in Brevo (Senders, Domains & "
        "Dedicated IPs -> Senders); Brevo emails that address a confirmation link.",
    ),
    (
        ("quota", "credit", "sending limit", "daily limit", "blocked", "suspended"),
        "The Brevo account cannot send right now (daily quota, plan limit or "
        "suspension). Check the plan and the sending limits in the Brevo dashboard.",
    ),
)


def _provider_hint(detail, hints):
    """First hint whose needles appear in the provider message, if any."""
    lowered = (detail or "").lower()
    return next((text for needles, text in hints if any(n in lowered for n in needles)), "")


def _provider_failure(label, status, body, hints, key_hint):
    """Build a user-facing delivery error from a provider error body."""
    detail = _summarise_provider_detail(body)
    hint = _provider_hint(detail, hints)
    if not hint and status in (401, 403):
        hint = key_hint
    message = f"{label} rejected the message ({status}): {detail}"
    if not message.endswith((".", "!", "?")):
        message = f"{message}."
    return f"{message} {hint}" if hint else message


def _sendgrid_failure(status, body):
    """Translate a SendGrid error payload into an actionable message."""
    return _provider_failure(
        "SendGrid",
        status,
        body,
        SENDGRID_HINTS,
        (
            "The API key was rejected: check SENDGRID_API_KEY is current, has no stray "
            "whitespace, and grants Mail Send (or Full Access)."
        ),
    )


def _brevo_failure(status, body):
    """Translate a Brevo error payload into an actionable message."""
    return _provider_failure("Brevo", status, body, BREVO_HINTS, BREVO_KEY_HINT)


def _response_header(response, name):
    """Read a response header defensively: some transports fake responses in tests."""
    headers = getattr(response, "headers", None)
    getter = getattr(headers, "get", None)
    return getter(name) if getter else None


def _read_error_body(exc):
    """Best-effort read of an error response body (it may be absent)."""
    try:
        body = exc.read()
    except Exception:  # pragma: no cover - defensive, transport dependent
        return ""
    return (body or b"").decode("utf-8", errors="ignore")


def _send_via_sendgrid(*, subject, text_content, html_content, recipients, attachments, from_email):
    payload = {
        "from": {"email": from_email},
        "personalizations": [
            {
                "to": [{"email": address} for address in recipients],
                "subject": subject,
            }
        ],
        "reply_to": {"email": from_email},
        "headers": {
            "X-Auto-Response-Suppress": "All",
        },
        "content": [
            {"type": "text/plain", "value": text_content},
            {"type": "text/html", "value": html_content},
        ],
    }
    if attachments:
        payload["attachments"] = [
            {
                "content": base64.b64encode(content).decode("ascii"),
                "type": mimetype,
                "filename": filename,
                "disposition": "attachment",
            }
            for filename, content, mimetype in attachments
        ]

    request = urlrequest.Request(
        SENDGRID_SEND_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_setting('SENDGRID_API_KEY')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(request, timeout=_timeout()) as response:
            if response.status >= 400:
                body = _read_error_body(response)
                raise InvoiceEmailError(_sendgrid_failure(response.status, body))
            return _response_header(response, "X-Message-Id")
    except urlerror.HTTPError as exc:
        body = _read_error_body(exc)
        raise InvoiceEmailError(_sendgrid_failure(exc.code, body)) from exc
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise InvoiceEmailError(f"Could not reach the SendGrid API: {exc}") from exc


def _send_via_brevo(*, subject, text_content, html_content, recipients, attachments, from_email):
    payload = {
        "sender": {"email": from_email},
        "to": [{"email": address} for address in recipients],
        "subject": subject,
        "replyTo": {"email": from_email},
    }
    # Brevo wants at least one body part and rejects an empty one, so omit blanks.
    if text_content:
        payload["textContent"] = text_content
    if html_content:
        payload["htmlContent"] = html_content
    if attachments:
        payload["attachment"] = [
            {
                "name": filename,
                "content": base64.b64encode(content).decode("ascii"),
            }
            for filename, content, mimetype in attachments
        ]

    request = urlrequest.Request(
        BREVO_SEND_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": _provider_api_key(BREVO_PROVIDER),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(request, timeout=_timeout()) as response:
            if response.status >= 400:
                body = _read_error_body(response)
                raise InvoiceEmailError(_brevo_failure(response.status, body))
            return _brevo_message_id(response)
    except urlerror.HTTPError as exc:
        body = _read_error_body(exc)
        raise InvoiceEmailError(_brevo_failure(exc.code, body)) from exc
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise InvoiceEmailError(f"Could not reach the Brevo API: {exc}") from exc


def _send_via_smtp(*, subject, text_content, html_content, recipients, attachments, from_email):
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=list(recipients),
        connection=get_connection(fail_silently=False),
        headers={
            "X-Auto-Response-Suppress": "All",
        },
    )
    if html_content:
        email.attach_alternative(html_content, "text/html")
    for filename, content, mimetype in attachments:
        email.attach(filename, content, mimetype)

    try:
        email.send(fail_silently=False)
    except smtplib.SMTPAuthenticationError as exc:
        user = _setting("EMAIL_HOST_USER", "the configured SMTP user")
        raise InvoiceEmailError(
            f"SMTP authentication failed for {user} ({exc}). {SMTP_AUTH_HINT}"
        ) from exc
    except (socket_timeout, TimeoutError, OSError, smtplib.SMTPServerDisconnected) as exc:
        raise InvoiceEmailError(_smtp_unreachable_error(exc)) from exc
    except ValueError as exc:
        raise InvoiceEmailError(_smtp_settings_error(exc)) from exc
    except smtplib.SMTPException as exc:
        raise InvoiceEmailError(f"SMTP delivery failed: {exc}") from exc


def send_email_message(*, subject, recipients, text_content="", html_content=None, attachments=(), from_email=None):
    """Deliver a single email through whichever provider is configured."""
    provider = validate_email_configuration()

    addresses = [address for address in recipients if address]
    if not addresses:
        raise EmailConfigurationError("No recipient address was provided for this email.")

    sender = from_email or _sender_for(provider)
    payload = {
        "subject": subject,
        "text_content": text_content or "",
        "html_content": html_content,
        "recipients": addresses,
        "attachments": _normalise_attachments(attachments),
        "from_email": sender,
    }

    message_id = None
    try:
        if provider == SENDGRID_PROVIDER:
            message_id = _send_via_sendgrid(**payload)
        elif provider == BREVO_PROVIDER:
            message_id = _send_via_brevo(**payload)
        else:
            _send_via_smtp(**payload)
    except InvoiceEmailError as exc:
        logger.error(
            "Email delivery via %s failed (to=%s, subject=%r): %s",
            provider,
            addresses,
            subject,
            exc,
            exc_info=True,
        )
        raise

    # The provider id is the only handle for chasing a message that was accepted but
    # never arrived, so record it alongside the send.
    logger.info(
        "Email accepted by %s (to=%s, subject=%r, provider_message_id=%s)",
        provider,
        addresses,
        subject,
        message_id or "unknown",
    )


def send_invoice_email(invoice):
    subject, text_content, html_content = _build_invoice_email_content(invoice)
    pdf_bytes = generate_invoice_pdf(invoice).read()
    send_email_message(
        subject=subject,
        recipients=[invoice.client_email],
        text_content=text_content,
        html_content=html_content,
        attachments=[(f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")],
    )


def _sendgrid_credits():
    """Best-effort credit balance; returns None when the key cannot read it."""
    request = urlrequest.Request(
        SENDGRID_CREDITS_URL,
        headers={"Authorization": f"Bearer {_setting('SENDGRID_API_KEY')}"},
        method="GET",
    )
    try:
        with urlrequest.urlopen(request, timeout=_timeout()) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except (urlerror.HTTPError, urlerror.URLError, TimeoutError, OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) and "remain" in payload else None


def _probe_sendgrid():
    request = urlrequest.Request(
        SENDGRID_SCOPES_URL,
        headers={"Authorization": f"Bearer {_setting('SENDGRID_API_KEY')}"},
        method="GET",
    )
    try:
        with urlrequest.urlopen(request, timeout=_timeout()) as response:
            payload = response.read().decode("utf-8", errors="ignore")
    except urlerror.HTTPError as exc:
        body = _read_error_body(exc)
        detail = f"SendGrid rejected the API key (HTTP {exc.code})."
        if body:
            detail = f"{detail} {body}"
        return {"ok": False, "detail": detail}
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "detail": f"Could not reach the SendGrid API: {exc}"}

    try:
        scopes = json.loads(payload).get("scopes")
    except (ValueError, AttributeError):
        scopes = None

    if scopes is None:
        detail = "SendGrid accepted the API key."
    elif "mail.send" in scopes:
        detail = f"SendGrid accepted the API key with mail.send ({len(scopes)} scopes)."
    else:
        return {
            "ok": False,
            "detail": (
                "The API key is valid but does not grant mail.send, so email cannot be "
                "sent. Create a key with Mail Send (or Full Access) and update "
                "SENDGRID_API_KEY."
            ),
            "scopes": scopes,
        }

    credits = _sendgrid_credits()
    # A zero balance only means "out of credits" when the plan tracks credits at all
    # (total is set); daily-limit plans report 0/0 while working normally.
    if credits is not None and credits.get("total") and not credits.get("remain"):
        return {
            "ok": False,
            "detail": (
                f"SendGrid accepted the API key but reports 0 of {credits['total']} email "
                "credits remaining, which makes every send fail with 401 Maximum credits "
                "exceeded. Restore the plan or quota on the SendGrid account."
            ),
            "credits": credits,
        }
    if credits is not None and credits.get("total"):
        detail = f"{detail} Credits remaining: {credits['remain']} of {credits['total']}."
    return {"ok": True, "detail": detail}


def _probe_smtp():
    try:
        connection = get_connection(fail_silently=False)
        connection.open()
        connection.close()
    except smtplib.SMTPAuthenticationError as exc:
        user = _setting("EMAIL_HOST_USER", "the configured SMTP user")
        return {"ok": False, "detail": f"SMTP authentication failed for {user} ({exc}). {SMTP_AUTH_HINT}"}
    except (socket_timeout, TimeoutError, OSError, smtplib.SMTPServerDisconnected) as exc:
        return {"ok": False, "detail": _smtp_unreachable_error(exc)}
    except ValueError as exc:
        return {"ok": False, "detail": _smtp_settings_error(exc)}
    except smtplib.SMTPException as exc:
        return {"ok": False, "detail": f"SMTP connection failed: {exc}"}
    return {"ok": True, "detail": "SMTP connection and authentication succeeded."}


def _brevo_email_credits(payload):
    """Remaining email allowance reported by /v3/account, when identifiable."""
    for key in ("emailCredits", "credits"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    for entry in payload.get("plan") or []:
        if not isinstance(entry, dict):
            continue
        credits = entry.get("credits")
        if isinstance(credits, int) and "sms" not in str(entry.get("creditsType", "")).lower():
            return credits
    return None


def _brevo_message_id(response):
    """Brevo echoes the id used to find this message in its delivery log."""
    try:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except (ValueError, AttributeError):
        return None
    return payload.get("messageId") if isinstance(payload, dict) else None


def _probe_brevo():
    request = urlrequest.Request(
        BREVO_ACCOUNT_URL,
        headers={"api-key": _provider_api_key(BREVO_PROVIDER), "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlrequest.urlopen(request, timeout=_timeout()) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except urlerror.HTTPError as exc:
        body = _read_error_body(exc)
        detail = _summarise_provider_detail(body) if body else ""
        hint = _provider_hint(detail, BREVO_HINTS)
        if exc.code == 403 and not hint:
            # Brevo answers 401 for an unknown key, so 403 means the key is real but
            # is not allowed to read account details (a transactional-only key, for
            # example). Reporting that as a bad key would send setup astray.
            return {
                "ok": True,
                "detail": (
                    "Brevo accepted the API key but it may not read account details "
                    "(HTTP 403), so the email allowance cannot be reported. Grant the "
                    "Account permission on the key, or ignore this: sending is "
                    "unaffected."
                    + (f" Brevo said: {detail}." if detail else "")
                ),
            }
        message = f"Brevo refused the request (HTTP {exc.code})."
        if detail:
            message = f"{message} {detail}"
        if hint:
            message = f"{message} {hint}"
        return {"ok": False, "detail": message}
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "detail": f"Could not reach the Brevo API: {exc}"}
    except ValueError as exc:
        return {"ok": False, "detail": f"Brevo returned an unreadable response: {exc}"}

    if not isinstance(payload, dict):
        return {"ok": True, "detail": "Brevo accepted the API key."}

    # Reported for information only: Brevo rejects each send with the real reason,
    # and free plans meter per day rather than per credit, so a zero here is not
    # proof that sending is broken.
    credits = _brevo_email_credits(payload)
    detail = "Brevo accepted the API key."
    if credits is not None:
        detail = f"{detail} Email allowance reported: {credits}."
    return {"ok": True, "detail": detail, "email_credits": credits}


def probe_email_provider(provider=None):
    """Open a real connection to the provider without sending a message."""
    provider = provider or validate_email_configuration()
    if provider == SENDGRID_PROVIDER:
        return _probe_sendgrid()
    if provider == BREVO_PROVIDER:
        return _probe_brevo()
    return _probe_smtp()


def _sanitized_env_notes():
    """Report which provider env values carried stray whitespace or quotes."""
    notes = {}
    names = ["SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL", "BREVO_API_KEY", "BREVO_FROM_EMAIL"]
    names += ["EMAIL_HOST_USER", "EMAIL_HOST", "EMAIL_PROVIDER"]
    for name in names:
        raw = os.environ.get(name)
        if raw and str(raw).strip() != _clean(raw):
            notes[name] = "Stray whitespace or quotes were removed when this value was loaded."
    return notes


def email_diagnostics(probe=False):
    """Return a non-sensitive snapshot of the active email configuration."""
    try:
        provider = resolve_provider()
    except EmailConfigurationError:
        provider = None

    info = {
        "provider": provider,
        "explicit_provider": str(_setting("EMAIL_PROVIDER")).strip() or None,
        "ready": False,
        "problems": [],
        "warnings": [],
        "on_render": _is_render(),
        "timeout_seconds": getattr(settings, "EMAIL_TIMEOUT", None),
        "default_from_email": _setting("DEFAULT_FROM_EMAIL") or None,
        "sendgrid_api_key_configured": bool(_setting("SENDGRID_API_KEY")),
        "sendgrid_api_key_prefix": (_setting("SENDGRID_API_KEY") or "")[:3] or None,
        "sendgrid_api_key_length": len(_setting("SENDGRID_API_KEY") or ""),
        "sendgrid_from_email": _setting("SENDGRID_FROM_EMAIL") or None,
        "brevo_api_key_configured": bool(_setting("BREVO_API_KEY")),
        "brevo_api_key_prefix": (_setting("BREVO_API_KEY") or "")[:3] or None,
        "brevo_api_key_length": len(_setting("BREVO_API_KEY") or ""),
        "brevo_from_email": _setting("BREVO_FROM_EMAIL") or None,
        "http_providers_configured": configured_http_providers(),
        "env_values_sanitized": _sanitized_env_notes(),
        "smtp_host": _setting("EMAIL_HOST") or None,
        "smtp_port": getattr(settings, "EMAIL_PORT", None),
        "smtp_use_tls": bool(getattr(settings, "EMAIL_USE_TLS", False)),
        "smtp_use_ssl": bool(getattr(settings, "EMAIL_USE_SSL", False)),
        "smtp_user_configured": bool(_setting("EMAIL_HOST_USER")),
        "smtp_password_configured": bool(_setting("EMAIL_HOST_PASSWORD")),
    }

    try:
        info["provider"] = validate_email_configuration()
        info["ready"] = True
    except EmailConfigurationError as exc:
        info["problems"].append(str(exc))

    if info["on_render"] and info["provider"] == SMTP_PROVIDER and info["smtp_host"]:
        info["warnings"].append(SMTP_EGRESS_BLOCKED_HINT)

    if len(info["http_providers_configured"]) > 1:
        info["warnings"].append(
            "More than one HTTP provider key is configured ("
            + ", ".join(info["http_providers_configured"])
            + f"); {info['provider']} is used because it comes first. Set EMAIL_PROVIDER "
            "to the provider you want so the choice is explicit."
        )

    if info["provider"] in HTTP_PROVIDERS and (info["smtp_user_configured"] or info["smtp_password_configured"]):
        info["warnings"].append(
            f"Email is delivered through the {HTTP_PROVIDERS[info['provider']]['label']} "
            "HTTP API, so the EMAIL_HOST_* settings are not used."
        )

    sender = _provider_sender(info["provider"]) if info["provider"] in HTTP_PROVIDERS else ""
    if sender and sender.rpartition("@")[2].lower() in FREEMAIL_DOMAINS:
        info["warnings"].append(
            f"{HTTP_PROVIDERS[info['provider']]['from_email']} is {sender}, a consumer "
            "mailbox. Providers only send from an address they have verified, so add it "
            "first: SendGrid under Settings -> Sender Authentication -> Single Sender "
            "Verification, Brevo under Senders, Domains & Dedicated IPs -> Senders."
        )

    if info["sendgrid_api_key_configured"] and info["sendgrid_api_key_prefix"] != "SG.":
        info["warnings"].append(
            "SENDGRID_API_KEY does not start with SG.; SendGrid API keys use that "
            "prefix, so the value may be truncated or is a different credential."
        )

    if info["brevo_api_key_configured"] and not _setting("BREVO_API_KEY").startswith(BREVO_KEY_PREFIX):
        info["warnings"].append(
            f"BREVO_API_KEY does not start with {BREVO_KEY_PREFIX}; Brevo API keys use "
            "that prefix, so the value may be truncated or is a different credential."
        )

    if probe:
        if info["ready"]:
            info["probe"] = probe_email_provider(info["provider"])
        else:
            info["probe"] = {
                "ok": False,
                "detail": "Email delivery is not configured; resolve the reported problems first.",
            }

    return info
