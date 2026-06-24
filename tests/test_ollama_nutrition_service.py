import unittest

from app.services.ollama_nutrition_service import OllamaNutritionService


class _FakeGeminiResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeGeminiModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.call_count = 0

    def generate_content(self, **kwargs):
        self.call_count += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeGeminiResponse(outcome)


class _FakeGeminiClient:
    def __init__(self, outcomes):
        self.models = _FakeGeminiModels(outcomes)


class _FakeOpenAIMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeOpenAIChoice:
    def __init__(self, content: str):
        self.message = _FakeOpenAIMessage(content)


class _FakeOpenAIResponse:
    def __init__(self, content: str):
        self.choices = [_FakeOpenAIChoice(content)]


class _FakeOpenAICompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.call_count = 0
        self.last_kwargs = None

    def create(self, **kwargs):
        self.call_count += 1
        self.last_kwargs = kwargs
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeOpenAIResponse(outcome)


class _FakeOpenAIChat:
    def __init__(self, outcomes):
        self.completions = _FakeOpenAICompletions(outcomes)


class _FakeOpenAIClient:
    def __init__(self, outcomes):
        self.chat = _FakeOpenAIChat(outcomes)


def _build_gemini_service(outcomes) -> OllamaNutritionService:
    service = object.__new__(OllamaNutritionService)
    service.backend = "gemini"
    service.model = "gemini-test"
    service.client = _FakeGeminiClient(outcomes)
    service.gemini_max_retries = 1
    service.gemini_retry_base_seconds = 0.0
    service.gemini_retry_max_seconds = 0.0
    service.gemini_quota_cooldown_seconds = 60
    service._gemini_unavailable_until = 0.0
    return service


def _build_openai_service(outcomes) -> OllamaNutritionService:
    service = object.__new__(OllamaNutritionService)
    service.backend = "openai"
    service.model = "gpt-test"
    service.client = _FakeOpenAIClient(outcomes)
    service.openai_max_retries = 1
    service.openai_retry_base_seconds = 0.0
    service.openai_retry_max_seconds = 0.0
    service.openai_timeout_seconds = 30
    service.gemini_max_retries = 0
    service.gemini_retry_base_seconds = 0.0
    service.gemini_retry_max_seconds = 0.0
    service.gemini_quota_cooldown_seconds = 0
    service._gemini_unavailable_until = 0.0
    return service


class OllamaNutritionServiceGeminiTests(unittest.TestCase):
    def test_gemini_503_retries_once(self):
        service = _build_gemini_service(
            [
                RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand."),
                '{"ok": true}',
            ]
        )

        result = service.generate_text("prompt", temperature=0.0)

        self.assertEqual(result, '{"ok": true}')
        self.assertEqual(service.client.models.call_count, 2)

    def test_gemini_daily_quota_enters_cooldown(self):
        service = _build_gemini_service(
            [
                RuntimeError(
                    "429 RESOURCE_EXHAUSTED. Quota exceeded for quotaId "
                    "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
                ),
                '{"should_not_call": true}',
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "Gemini request failed"):
            service.generate_text("prompt", temperature=0.0)
        with self.assertRaisesRegex(RuntimeError, "temporarily disabled"):
            service.generate_text("prompt", temperature=0.0)

        self.assertEqual(service.client.models.call_count, 1)


class OllamaNutritionServiceOpenAITests(unittest.TestCase):
    def test_openai_generates_json_with_json_response_format(self):
        service = _build_openai_service(['{"ok": true}'])

        result = service.generate_text("prompt", temperature=0.1)

        self.assertEqual(result, '{"ok": true}')
        completions = service.client.chat.completions
        self.assertEqual(completions.call_count, 1)
        self.assertEqual(completions.last_kwargs["model"], "gpt-test")
        self.assertEqual(completions.last_kwargs["response_format"], {"type": "json_object"})

    def test_openai_429_retries_once(self):
        service = _build_openai_service(
            [
                RuntimeError("429 rate_limit_exceeded"),
                '{"ok": true}',
            ]
        )

        result = service.generate_text("prompt", temperature=0.0)

        self.assertEqual(result, '{"ok": true}')
        self.assertEqual(service.client.chat.completions.call_count, 2)


if __name__ == "__main__":
    unittest.main()
