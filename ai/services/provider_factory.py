from django.conf import settings

from .providers.base import AIServiceError
from .providers.gemini_provider import GeminiProvider
from .providers.openai_provider import OpenAIProvider


def get_ai_provider():
    provider_name = str(getattr(settings, "AI_PROVIDER", "openai")).strip().lower()
    if provider_name == "openai":
        return OpenAIProvider()
    if provider_name == "gemini":
        return GeminiProvider()
    raise AIServiceError(f"Unsupported AI provider '{provider_name}'. Use 'openai' or 'gemini'.", status_code=500)
