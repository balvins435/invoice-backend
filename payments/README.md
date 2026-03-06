# Payments Integration Guide (M-Pesa Daraja)

This guide covers local sandbox setup and API payloads for frontend integration.

## 1. Required Environment Variables (Sandbox)

Add these to `backend/.env`:

```env
# M-Pesa Daraja
MPESA_CONSUMER_KEY=your_safaricom_sandbox_consumer_key
MPESA_CONSUMER_SECRET=your_safaricom_sandbox_consumer_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_lipa_na_mpesa_passkey
MPESA_CALLBACK_URL=https://your-public-domain.com/api/payments/mpesa/callback/
MPESA_BASE_URL=https://sandbox.safaricom.co.ke
MPESA_TRANSACTION_TYPE=CustomerPayBillOnline
```

Notes:
- `MPESA_CALLBACK_URL` must be publicly reachable by Safaricom.
- For local development, use a tunnel (for example ngrok/cloudflared) and map to your local backend.
- `MPESA_TRANSACTION_TYPE` default is `CustomerPayBillOnline`.

## 2. Payment Flow

1. Frontend creates or fetches an invoice.
2. Frontend calls `initiate-stk` with invoice id and customer phone.
3. Customer receives STK push on phone and enters PIN.
4. Safaricom sends callback to backend.
5. Backend marks transaction complete, marks invoice `paid`, and auto-creates receipt.

## 3. API Endpoints

Base path: `/api/payments/`

- `POST transactions/initiate-stk/`
- `POST mpesa/callback/` (Safaricom server-to-server)
- `POST transactions/{id}/confirm/` (manual/testing)
- `GET transactions/`
- `GET transactions/{id}/`

## 4. Initiate STK Push

### Request

`POST /api/payments/transactions/initiate-stk/`

```json
{
  "invoice_id": 12,
  "phone_number": "0712345678",
  "amount": "1500.00"
}
```

Notes:
- `phone_number` is normalized to Daraja format (`2547XXXXXXXX`).
- `amount` is optional; if omitted, invoice `total_amount` is used.

### Success Response (201)

```json
{
  "transaction": {
    "id": 44,
    "reference": "PAY-0A12BC34DE56F789",
    "business": 3,
    "invoice": 12,
    "invoice_number": "INV-0012",
    "phone_number": "254712345678",
    "amount": "1500.00",
    "currency": "KES",
    "status": "pending",
    "merchant_request_id": "29115-34620561-1",
    "checkout_request_id": "ws_CO_191220191020363925",
    "mpesa_receipt_number": "",
    "result_code": "0",
    "result_description": "Success. Request accepted for processing",
    "raw_request": {},
    "raw_response": {},
    "callback_payload": {},
    "paid_at": null,
    "created_at": "2026-03-06T10:30:00Z",
    "updated_at": "2026-03-06T10:30:00Z"
  },
  "provider_response": {
    "MerchantRequestID": "29115-34620561-1",
    "CheckoutRequestID": "ws_CO_191220191020363925",
    "ResponseCode": "0",
    "ResponseDescription": "Success. Request accepted for processing",
    "CustomerMessage": "Success. Request accepted for processing"
  }
}
```

### Provider/Network Failure (502)

If Daraja rejects the request or provider call fails, API returns `502` with saved failure details:

```json
{
  "transaction": {
    "status": "failed",
    "result_description": "Failed to initiate STK push: ..."
  },
  "provider_response": {
    "error": "..."
  }
}
```

## 5. Callback Payload (Daraja -> Backend)

Daraja posts to:

`POST /api/payments/mpesa/callback/`

Example payload:

```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "29115-34620561-1",
      "CheckoutRequestID": "ws_CO_191220191020363925",
      "ResultCode": 0,
      "ResultDesc": "The service request is processed successfully.",
      "CallbackMetadata": {
        "Item": [
          {"Name": "Amount", "Value": 1500.00},
          {"Name": "MpesaReceiptNumber", "Value": "QWE123RTY"},
          {"Name": "PhoneNumber", "Value": 254712345678}
        ]
      }
    }
  }
}
```

Backend ACK response:

```json
{
  "ResultCode": 0,
  "ResultDesc": "Accepted"
}
```

## 6. Manual Confirm Endpoint (Testing)

Use when simulating success/failure without Daraja callback.

### Request

`POST /api/payments/transactions/{id}/confirm/`

```json
{
  "success": true,
  "result_code": "0",
  "result_description": "Confirmed manually",
  "mpesa_receipt_number": "SIM123ABC"
}
```

### Result

- On `success: true`: transaction -> `completed`, invoice -> `paid`, receipt created if not existing.
- On `success: false`: transaction -> `failed`.

## 7. Frontend Integration Checklist

- Collect invoice id and payer phone number.
- Call `initiate-stk` after user taps "Pay with M-Pesa".
- Show a pending state: "Check your phone and enter M-Pesa PIN".
- Poll `GET /api/payments/transactions/?invoice_id={invoiceId}` until status changes.
- When status becomes `completed`, refresh invoice data and show receipt action.

## 8. Common Errors

- `400 Invalid phone number`:
  - Ensure Kenyan valid mobile number.
- `400 Invoice is already paid`:
  - Block duplicate payment attempts in UI.
- `502` on initiate:
  - Check Daraja credentials, passkey, callback URL, and internet reachability.

## 9. Local Callback Testing with Tunnel

Example with ngrok:

1. Run backend on port `8000`.
2. Start tunnel: `ngrok http 8000`
3. Set `MPESA_CALLBACK_URL=https://<ngrok-id>.ngrok-free.app/api/payments/mpesa/callback/`
4. Restart backend.
5. Trigger STK push and inspect callbacks in logs.
