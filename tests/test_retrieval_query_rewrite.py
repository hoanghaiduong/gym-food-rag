from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.config import settings
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition.workflow.retrieval_queries import WorkflowRetrievalQueriesMixin


class _FakeLlm:
    def __init__(self, response: str = "healthy budget protein carb rau", *, should_fail: bool = False) -> None:
        self.response = response
        self.should_fail = should_fail
        self.calls = 0

    def generate_text(self, prompt: str, temperature: float = 0.0) -> str:
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("quota")
        return self.response


class _DummyRetrievalWorkflow(WorkflowRetrievalQueriesMixin):
    def __init__(self, llm: _FakeLlm) -> None:
        self.llm = llm
        self._llm_retrieval_rewrite_enabled_override = None
        self._retrieval_instruction_rewrite_cache = {}
        self._retrieval_query_bundle_cache = {}

    def _compact_instruction_for_retrieval(self, instruction: str, *, limit: int = 8) -> str:
        return "compact fallback"


class RetrievalQueryRewriteTests(unittest.TestCase):
    def test_rewrite_cache_avoids_duplicate_llm_calls_for_same_instruction(self) -> None:
        workflow = _DummyRetrievalWorkflow(_FakeLlm())
        intent = NutritionIntent(goal="lose_weight", planning_strategy="budget_cut")

        with patch.object(settings, "RETRIEVAL_ENABLE_LLM_QUERY_REWRITE", True):
            first = workflow._rewrite_instruction_for_retrieval("healthy budget gym meal", intent)
            second = workflow._rewrite_instruction_for_retrieval("healthy budget gym meal", intent)

        self.assertEqual(first, "healthy budget protein carb rau")
        self.assertEqual(second, first)
        self.assertEqual(workflow.llm.calls, 1)

    def test_disabled_llm_query_rewrite_uses_deterministic_fallback(self) -> None:
        workflow = _DummyRetrievalWorkflow(_FakeLlm())
        intent = NutritionIntent(goal="lose_weight", planning_strategy="budget_cut")

        with patch.object(settings, "RETRIEVAL_ENABLE_LLM_QUERY_REWRITE", False):
            rewritten = workflow._rewrite_instruction_for_retrieval("healthy budget gym meal", intent)

        self.assertEqual(rewritten, "compact fallback")
        self.assertEqual(workflow.llm.calls, 0)

    def test_failed_llm_rewrite_is_cached_as_fallback(self) -> None:
        workflow = _DummyRetrievalWorkflow(_FakeLlm(should_fail=True))
        intent = NutritionIntent(goal="lose_weight", planning_strategy="budget_cut")

        with patch.object(settings, "RETRIEVAL_ENABLE_LLM_QUERY_REWRITE", True):
            first = workflow._rewrite_instruction_for_retrieval("healthy budget gym meal", intent)
            second = workflow._rewrite_instruction_for_retrieval("healthy budget gym meal", intent)

        self.assertEqual(first, "compact fallback")
        self.assertEqual(second, "compact fallback")
        self.assertEqual(workflow.llm.calls, 1)


if __name__ == "__main__":
    unittest.main()
