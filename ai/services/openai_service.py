import json

from django.conf import settings
from openai import OpenAI


class OpenAIServiceError(Exception):
    pass


def _get_client():
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        raise OpenAIServiceError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


def _extract_json_payload(raw_content):
    if not raw_content:
        raise OpenAIServiceError("AI service returned an empty response.")

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise OpenAIServiceError("AI service did not return valid JSON.")
        try:
            return json.loads(raw_content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise OpenAIServiceError("AI service returned malformed JSON.") from exc


def generate_json_response(system_prompt, user_prompt, model="gpt-4o-mini"):
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return _extract_json_payload(content)
