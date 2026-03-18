import base64
import json
import logging
from datetime import datetime
from decimal import Decimal
from urllib import error, request

import phonenumbers
from django.conf import settings
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone

from invoice.models import Receipt
from payments.models import PaymentTransaction

logger = logging.getLogger(__name__)


class MpesaService:
    """Service for initiating and confirming M-Pesa STK payments."""

    def __init__(self):
        self.consumer_key = getattr(settings, "MPESA_CONSUMER_KEY", "")
        self.consumer_secret = getattr(settings, "MPESA_CONSUMER_SECRET", "")
        self.shortcode = getattr(settings, "MPESA_SHORTCODE", "")
        self.passkey = getattr(settings, "MPESA_PASSKEY", "")
        self.callback_url = getattr(settings, "MPESA_CALLBACK_URL", "")
        self.base_url = getattr(settings, "MPESA_BASE_URL", "https://sandbox.safaricom.co.ke")
        self.transaction_type = getattr(settings, "MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline")

    def _is_live_configured(self):
        return all([
            self.consumer_key,
            self.consumer_secret,
            self.shortcode,
            self.passkey,
            self.callback_url,
            self.base_url,
        ])

    @staticmethod
    def normalize_msisdn(phone_number):
        try:
            parsed = phonenumbers.parse(phone_number, "KE")
        except phonenumbers.NumberParseException as exc:
            raise ValueError("Invalid phone number.") from exc
        if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number.")

        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        if not e164.startswith("+254"):
            raise ValueError("Only Kenyan phone numbers are supported for M-Pesa.")

        return e164[1:]  # Daraja expects 2547XXXXXXXX format.

    def _request_access_token(self):
        credentials = f"{self.consumer_key}:{self.consumer_secret}".encode("utf-8")
        auth_header = base64.b64encode(credentials).decode("utf-8")

        token_url = f"{self.base_url.rstrip('/')}/oauth/v1/generate?grant_type=client_credentials"
        req = request.Request(
            token_url,
            headers={"Authorization": f"Basic {auth_header}"},
            method="GET",
        )

        with request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        access_token = payload.get("access_token", "")
        if not access_token:
            raise ValueError("Unable to retrieve M-Pesa access token.")
        return access_token

    def _build_password(self, timestamp):
        return base64.b64encode(f"{self.shortcode}{self.passkey}{timestamp}".encode("utf-8")).decode("utf-8")

    def _post_json(self, url, data, headers):
        req = request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def initiate_stk_push(self, invoice, phone_number, amount=None, idempotency_key=None):
        amount_value = Decimal(amount if amount is not None else invoice.total_amount)
        if amount_value <= 0:
            raise ValueError("Amount must be greater than zero.")

        msisdn = self.normalize_msisdn(phone_number)
        if idempotency_key:
            existing = PaymentTransaction.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing, existing.raw_response

        transaction = PaymentTransaction.objects.create(
            business=invoice.business,
            invoice=invoice,
            idempotency_key=idempotency_key,
            phone_number=msisdn,
            amount=amount_value,
            currency=getattr(invoice, "currency", "KES"),
            status=PaymentTransaction.STATUS_PENDING,
        )

        request_payload = {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "phone_number": msisdn,
            "amount": str(amount_value),
        }

        if not self._is_live_configured():
            transaction.raw_request = request_payload
            transaction.raw_response = {
                "response_code": "0",
                "response_description": "Simulated STK push request accepted.",
                "checkout_request_id": f"ws_CO_{transaction.reference}",
                "merchant_request_id": f"ms_MR_{transaction.reference}",
            }
            transaction.checkout_request_id = transaction.raw_response["checkout_request_id"]
            transaction.merchant_request_id = transaction.raw_response["merchant_request_id"]
            transaction.save(update_fields=[
                "raw_request",
                "raw_response",
                "checkout_request_id",
                "merchant_request_id",
                "updated_at",
            ])
            return transaction, transaction.raw_response

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": self._build_password(timestamp),
            "Timestamp": timestamp,
            "TransactionType": self.transaction_type,
            "Amount": int(amount_value),
            "PartyA": msisdn,
            "PartyB": self.shortcode,
            "PhoneNumber": msisdn,
            "CallBackURL": self.callback_url,
            "AccountReference": invoice.invoice_number[:12],
            "TransactionDesc": f"INV {invoice.invoice_number}"[:13],
        }

        transaction.raw_request = payload

        try:
            token = self._request_access_token()
            response_payload = self._post_json(
                f"{self.base_url.rstrip('/')}/mpesa/stkpush/v1/processrequest",
                payload,
                headers={"Authorization": f"Bearer {token}"},
            )

            transaction.raw_response = response_payload
            transaction.checkout_request_id = response_payload.get("CheckoutRequestID", "")
            transaction.merchant_request_id = response_payload.get("MerchantRequestID", "")
            transaction.result_code = response_payload.get("ResponseCode", "")
            transaction.result_description = response_payload.get("ResponseDescription", "")
            if str(transaction.result_code) != "0":
                transaction.status = PaymentTransaction.STATUS_FAILED
            transaction.save()
            return transaction, response_payload

        except (ValueError, error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            logger.exception("STK push request failed for invoice=%s", invoice.id)
            transaction.status = PaymentTransaction.STATUS_FAILED
            transaction.result_description = f"Failed to initiate STK push: {exc}"
            transaction.raw_response = {"error": str(exc)}
            transaction.save(update_fields=["status", "result_description", "raw_response", "updated_at"])
            return transaction, transaction.raw_response

    @classmethod
    def confirm_transaction(
        cls,
        transaction,
        *,
        success,
        result_code,
        result_description,
        receipt_number="",
        callback_payload=None,
    ):
        callback_payload = callback_payload or {}

        with db_transaction.atomic():
            if transaction.status == PaymentTransaction.STATUS_COMPLETED and success:
                transaction.callback_payload = callback_payload
                transaction.save(update_fields=["callback_payload", "updated_at"])
                return transaction

            transaction.callback_payload = callback_payload
            transaction.result_code = str(result_code)
            transaction.result_description = result_description or ""

            if success:
                transaction.status = PaymentTransaction.STATUS_COMPLETED
                transaction.mpesa_receipt_number = receipt_number or transaction.mpesa_receipt_number
                transaction.paid_at = timezone.now()

                invoice = transaction.invoice
                notes = f"Auto-generated from M-Pesa transaction {transaction.reference}."
                if transaction.mpesa_receipt_number:
                    notes = f"M-Pesa receipt: {transaction.mpesa_receipt_number}."

                Receipt.objects.create(
                    invoice=invoice,
                    payment_method="mobile_money",
                    payment_date=timezone.localdate(),
                    amount_paid=transaction.amount,
                    currency=getattr(invoice, "currency", "KES"),
                    reference=transaction.mpesa_receipt_number or transaction.reference,
                    notes=notes,
                )

                total_paid = (
                    Receipt.objects.filter(invoice=invoice)
                    .aggregate(total=Sum("amount_paid"))
                    .get("total")
                    or Decimal("0.00")
                )
                remaining_balance = invoice.total_amount - total_paid
                if remaining_balance <= Decimal("0.00") and invoice.status != "paid":
                    invoice.status = "paid"
                    invoice.paid_at = timezone.now()
                    invoice.save(update_fields=["status", "paid_at"])
            else:
                transaction.status = PaymentTransaction.STATUS_FAILED

            transaction.save()

        return transaction
