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


if __name__ == "__main__":
    unittest.main()
