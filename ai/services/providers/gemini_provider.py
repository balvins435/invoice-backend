import json
import logging
from urllib import error, parse, request

from django.conf import settings

from .base import AIServiceError, BaseAIProvider, extract_json_payload

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent"

    def __init__(self):
        self.api_key = str(getattr(settings, "GEMINI_API_KEY", "") or "").strip()
        if not self.api_key:
            raise AIServiceError("GEMINI_API_KEY is not configured.")
        self.default_model = str(getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash") or "gemini-2.0-flash").strip()
        self.api_version = str(getattr(settings, "GEMINI_API_VERSION", "v1") or "v1").strip()
        self.timeout = getattr(settings, "AI_PROVIDER_TIMEOUT", 30)

    def generate_json_response(self, system_prompt, user_prompt, model=None):
        selected_model = str(model or self.default_model or "gemini-2.0-flash").strip()
        if selected_model.startswith("models/"):
            selected_model = selected_model.split("/", 1)[1]
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"{system_prompt}\n\n"
                                "Return valid JSON only. Do not include markdown fences.\n\n"
                                f"{user_prompt}"
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }
        endpoint = self.BASE_URL.format(
            api_version=parse.quote(self.api_version, safe=""),
            model=parse.quote(selected_model, safe=".-"),
        )
        url = f"{endpoint}?{parse.urlencode({'key': self.api_key})}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            provider_message = self._extract_error_message(error_body)
            logger.warning("Gemini HTTP error %s: %s", exc.code, provider_message or error_body)
            if exc.code in (401, 403):
                raise AIServiceError(
                    provider_message or "Gemini API key is invalid or not authorized.",
                    status_code=503,
                ) from exc
            if exc.code == 429:
                raise AIServiceError(
                    provider_message
                    or "AI assistant is temporarily unavailable because the Gemini quota has been exceeded. Try again later.",
                    status_code=503,
                ) from exc
            if exc.code == 400:
                raise AIServiceError(provider_message or "Gemini rejected the request payload.", status_code=502) from exc
            raise AIServiceError(provider_message or "Gemini returned an upstream service error.", status_code=502) from exc
        except error.URLError as exc:
            logger.warning("Gemini connectivity issue: %s", exc)
            raise AIServiceError(
                "AI assistant could not reach the Gemini provider. Please try again in a moment.",
                status_code=503,
            ) from exc
        except ValueError as exc:
            logger.warning("Gemini configuration issue: %s", exc)
            raise AIServiceError(
                f"Gemini configuration is invalid: {exc}",
                status_code=500,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected Gemini provider failure")
            raise AIServiceError(
                f"AI assistant failed unexpectedly while calling Gemini: {exc}",
                status_code=500,
            ) from exc

        text = self._extract_text(raw)
        return extract_json_payload(text)

    def _extract_error_message(self, error_body):
        if not error_body:
            return ""
        try:
            payload = json.loads(error_body)
        except json.JSONDecodeError:
            return error_body.strip()

        error_payload = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error_payload, dict):
            return str(error_payload.get("message") or "").strip()
        return error_body.strip()

    def _extract_text(self, payload):
        candidates = payload.get("candidates") or []
        if not candidates:
            raise AIServiceError("Gemini returned no candidate response.")

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text_chunks = [part.get("text", "") for part in parts if isinstance(part, dict)]
        text = "".join(text_chunks).strip()
        if not text:
            raise AIServiceError("Gemini returned an empty response.")
        return text
