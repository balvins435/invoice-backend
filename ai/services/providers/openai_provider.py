import logging

from django.conf import settings
from openai import APIConnectionError, APITimeoutError, APIStatusError, OpenAI, RateLimitError

from .base import AIServiceError, BaseAIProvider, extract_json_payload

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    def __init__(self):
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            raise AIServiceError("OPENAI_API_KEY is not configured.")
        self.client = OpenAI(api_key=api_key)
        self.default_model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    def generate_json_response(self, system_prompt, user_prompt, model=None):
        try:
            response = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit or quota issue: %s", exc)
            raise AIServiceError(
                "AI assistant is temporarily unavailable because the API quota has been exceeded. Add billing or try again later.",
                status_code=503,
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            logger.warning("OpenAI connectivity issue: %s", exc)
            raise AIServiceError(
                "AI assistant could not reach the AI provider. Please try again in a moment.",
                status_code=503,
            ) from exc
        except APIStatusError as exc:
            logger.exception("OpenAI API returned an unexpected status error")
            raise AIServiceError(
                "AI assistant failed to complete the request due to an upstream service error.",
                status_code=502,
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected OpenAI provider failure")
            raise AIServiceError(
                "AI assistant failed unexpectedly. Please try again shortly.",
                status_code=500,
            ) from exc

        content = response.choices[0].message.content
        return extract_json_payload(content)
