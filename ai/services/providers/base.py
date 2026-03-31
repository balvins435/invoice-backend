import json


class AIServiceError(Exception):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.status_code = status_code


def extract_json_payload(raw_content):
    if not raw_content:
        raise AIServiceError("AI service returned an empty response.")

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIServiceError("AI service did not return valid JSON.")
        try:
            return json.loads(raw_content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AIServiceError("AI service returned malformed JSON.") from exc


class BaseAIProvider:
    def generate_json_response(self, system_prompt, user_prompt, model=None):
        raise NotImplementedError
