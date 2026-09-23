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
  "sendgrid_api_key_prefix": "SG.",
  "sendgrid_api_key_length": 69,
  "sendgrid_from_email": "billing@yourdomain.com",
  "env_values_sanitized": {},
  "probe": { "ok": true, "detail": "SendGrid accepted the API key with mail.send (12 scopes)." }
}
```

* `problems` - blockers; email cannot be sent until they are resolved.
* `warnings` - advisories, for example that SMTP is selected on Render.
* `probe.ok` - the provider accepted the credentials (and, for SendGrid,
  that the key carries the `mail.send` scope).
* `sendgrid_from_email` / `sendgrid_api_key_prefix` / `sendgrid_api_key_length`
  - the From address and a safe fingerprint of the key, for spotting a truncated
  or swapped credential without exposing it.
* `env_values_sanitized` - values that carried stray whitespace or quotes.

### Troubleshooting a `502` on Render

Work through this list in order; items 1, 2, 3 and 5 are reported by the
diagnostics endpoint for you.

1. **`EMAIL_PROVIDER=sendgrid` disables the Gmail settings.** An explicit
   `EMAIL_PROVIDER` always wins, so `EMAIL_HOST`, `EMAIL_HOST_USER`,
   `EMAIL_HOST_PASSWORD`, `EMAIL_PORT` and `EMAIL_USE_TLS` are loaded but
   never used, and mail leaves over the SendGrid HTTP API instead. Diagnostics
   reports this as an `EMAIL_HOST_*` warning.
2. **`SENDGRID_FROM_EMAIL` must be a sender SendGrid has verified.** For
   anything else SendGrid answers `403` with "The from address does not match a
   verified Sender Identity". A consumer mailbox such as `you@gmail.com` cannot
   be domain-authenticated, so it has to be added under Settings -> Sender
   Authentication -> Single Sender Verification and confirmed through the email
   SendGrid sends. Diagnostics warns when the From address is a consumer mailbox.
3. **`SENDGRID_API_KEY` must be current and grant Mail Send.** A key that was
   deleted, rotated, or created without the Mail Send scope is rejected with
   `401`/`403`. `?probe=1` reads the key's scopes and reports whether
   `mail.send` is present.
4. **The SendGrid account itself must be in good standing.** SendGrid reuses
   `401` for account-level refusals, so a delivery error of
   `401 Maximum credits exceeded` means the credentials and sender were accepted
   and the account is the problem: an exhausted balance, a finished trial, or a
   review/suspension. Check Billing and Plan plus the alerts in the account, and
   look for SendGrid's own warning emails. `?probe=1` reads
   `/v3/user/credits` and reports the remaining balance when the key is allowed
   to see it.
5. **Watch for pasted whitespace.** Dashboard textareas happily store a trailing
   newline or wrapping quotes, and a stray newline in the API key makes SendGrid
   reject it. Values are stripped when they are read; any that needed stripping
   are listed under `env_values_sanitized`.
6. **A stale `EMAIL_PORT`/`EMAIL_USE_TLS` pair is harmless.** `EMAIL_USE_SSL`
   and `EMAIL_USE_TLS` are derived from `EMAIL_PORT` and normalised so only one
   of them is ever true, so a leftover `EMAIL_USE_TLS=True` next to
   `EMAIL_PORT=465` no longer fails at send time.

Provider refusals are rewritten for humans before they reach the UI, so SendGrid's
own sentence is shown instead of the raw JSON envelope, for example
`SendGrid rejected the message (401): Maximum credits exceeded.`

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
