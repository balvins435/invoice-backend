# Email Delivery Setup

All outbound app email (invoice emails, password resets) goes through one delivery
layer: `invoice/email_utils.py`.

## How the provider is chosen

`EMAIL_PROVIDER` selects the transport:

| `EMAIL_PROVIDER` | Transport | Notes |
| --- | --- | --- |
| *(empty)* | auto | SendGrid when `SENDGRID_API_KEY` is set, otherwise SMTP |
| `smtp` | SMTP relay | needs `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` |
| `sendgrid` | SendGrid HTTP API | needs `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL` |

Leaving `EMAIL_PROVIDER` empty is recommended: the deployment then uses whichever
provider actually has credentials.

## Why production failed with `502 (Bad Gateway)`

The API reports two different failure classes so they can be told apart in the
browser network tab:

| Status | Meaning | Response code |
| --- | --- | --- |
| `503` | Email delivery is not configured (no provider credentials) | `email_not_configured` |
| `502` | The provider was contacted and refused/failed | `email_delivery_failed` |

**Render free instances cannot send outbound traffic on ports 25, 465 or 587**
(Render docs, "Free instance types"), so SMTP - including Gmail - never works
there, no matter which credentials are configured. The deployment must use an
HTTP email API.

### Fix for the Render deployment

1. Create a SendGrid account and verify a sender identity (Settings -> Sender
   Authentication -> Single Sender Verification). Free tier covers 100 emails/day.
2. Create an API key with the "Mail Send" permission.
3. Add these environment variables to the Render service (Dashboard -> service ->
   Environment) and redeploy:

   ```text
   SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxx
   SENDGRID_FROM_EMAIL=the-verified-sender@yourdomain.com
   ```

   `EMAIL_PROVIDER` can stay unset; SendGrid is then selected automatically.
   If `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` are also present they are ignored.

Alternative: keep Gmail SMTP and move the service to a paid instance type, or use
an SMTP relay that listens on port 2525 (ports 25/465/587 only are blocked).

## Verifying a deployment

`GET /api/invoice/email-diagnostics/` reports the active configuration without
exposing secrets. Add `?probe=1` to open a real connection and authenticate:

```bash
curl -s -H "Authorization: Bearer <access-token>" \
  "https://<backend-host>/api/invoice/email-diagnostics/?probe=1"
```

```json
{
  "provider": "sendgrid",
  "ready": true,
  "problems": [],
  "warnings": [],
  "on_render": true,
  "sendgrid_api_key_configured": true,
  "probe": { "ok": true, "detail": "SendGrid accepted the API key." }
}
```

* `problems` - blockers; email cannot be sent until they are resolved.
* `warnings` - advisories, for example that SMTP is selected on Render.
* `probe.ok` - the provider accepted the credentials.

## Local development (Gmail SMTP)

1. Enable 2-step verification on the Google account.
2. Create an app password at https://myaccount.google.com/apppasswords.
3. Put it in `.env` (spaces are allowed, they are stripped on load):

   ```text
   EMAIL_PROVIDER=
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=you@gmail.com
   EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop
   DEFAULT_FROM_EMAIL=you@gmail.com
   ```

Gmail occasionally answers `535 Username and Password not accepted` for a valid
app password (throttling/suspicious sign-in). The API surfaces that message
directly, and a retry usually succeeds.

## Sending through the API

`POST /api/invoice/<id>/send_email/` returns:

* `200 {"status": "Invoice sent"}` - delivered, invoice marked `sent`.
* `502 {"code": "email_delivery_failed", "error": "..."}` - provider failure; the
  message contains the provider reason (for example `SendGrid rejected the
  message (403): sender not verified`).
* `503 {"code": "email_not_configured", "error": "..."}` - missing credentials.

Failures are also logged server-side with a full traceback, so they show up in
the Render log stream.
