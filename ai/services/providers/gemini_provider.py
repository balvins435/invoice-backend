import json
import logging
from urllib import error, parse, request

from django.conf import settings

from .base import AIServiceError, BaseAIProvider, extract_json_payload

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self):
        self.api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not self.api_key:
            raise AIServiceError("GEMINI_API_KEY is not configured.")
        self.default_model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
        self.timeout = getattr(settings, "AI_PROVIDER_TIMEOUT", 30)

    def generate_json_response(self, system_prompt, user_prompt, model=None):
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
        endpoint = self.BASE_URL.format(model=model or self.default_model)
        url = f"{endpoint}?key={parse.quote(self.api_key)}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            logger.warning("Gemini HTTP error %s: %s", exc.code, error_body)
            if exc.code in (401, 403):
                raise AIServiceError("Gemini API key is invalid or not authorized.", status_code=503) from exc
            if exc.code == 429:
                raise AIServiceError(
                    "AI assistant is temporarily unavailable because the Gemini quota has been exceeded. Try again later.",
                    status_code=503,
                ) from exc
            raise AIServiceError("Gemini returned an upstream service error.", status_code=502) from exc
        except error.URLError as exc:
            logger.warning("Gemini connectivity issue: %s", exc)
            raise AIServiceError(
                "AI assistant could not reach the Gemini provider. Please try again in a moment.",
                status_code=503,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected Gemini provider failure")
            raise AIServiceError(
                "AI assistant failed unexpectedly while calling Gemini.",
                status_code=500,
            ) from exc

        text = self._extract_text(raw)
        return extract_json_payload(text)

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
