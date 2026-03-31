from .provider_factory import get_ai_provider
from .providers.base import AIServiceError

# Backward-compatible alias for existing imports.
OpenAIServiceError = AIServiceError


def generate_json_response(system_prompt, user_prompt, model=None):
    provider = get_ai_provider()
    return provider.generate_json_response(system_prompt, user_prompt, model=model)
