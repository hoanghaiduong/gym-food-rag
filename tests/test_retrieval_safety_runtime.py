from __future__ import annotations

import unittest

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition.workflow.candidate_pool_support import WorkflowCandidatePoolSupportMixin
from app.services.nutrition.workflow.retrieval_queries import WorkflowRetrievalQueriesMixin
from app.services.nutrition.workflow.retrieval_support_queries import WorkflowRetrievalSupportQueriesMixin


class _DummyCandidatePoolSupportWorkflow(WorkflowCandidatePoolSupportMixin):
    def _unique_retrieval_terms(self, values: list[str], *, limit: int | None = None) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = " ".join(str(value or "").lower().split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
            if limit is not None and len(unique) >= limit:
                break
        return unique


class _DummyRetrievalQueryWorkflow(WorkflowRetrievalQueriesMixin, WorkflowRetrievalSupportQueriesMixin):
    def __init__(self) -> None:
        self._llm_retrieval_rewrite_enabled_override = False
        self._retrieval_instruction_rewrite_cache = {}
        self._retrieval_query_bundle_cache = {}

    def _resolve_goal_family(self, profile, intent=None):  # type: ignore[override]
        return "maintain"

    def _resolve_retrieval_strategy(self, profile, intent=None):  # type: ignore[override]
        return "maintenance_training_support"

    def _build_retrieval_rerank_context(self, profile, request, intent=None):  # type: ignore[override]
        return {
            "dietary_preference": profile.get("dietary_preference") or "omnivore",
            "protein_anchors": ["thit ga", "trung", "ca"],
            "carb_anchors": ["gao", "khoai"],
            "produce_anchors": ["rau xanh"],
            "balanced_anchors": ["ca", "trung"],
            "must_include": ["gạo", "trứng"],
            "preferred_foods": ["thịt gà"],
            "excluded_foods": ["kẹo"],
            "allergy_tags": [],
            "expected_role_tags": ["protein_anchor", "carb_anchor", "post_workout_friendly"],
            "post_workout_meal": True,
            "satiety_preference": None,
            "balanced_meal_required": False,
        }

    def _prioritize_retrieval_terms(self, values, *, limit=None):  # type: ignore[override]
        return self._unique_retrieval_terms(list(values), limit=limit)

    def _unique_retrieval_terms(self, values, *, limit=None):  # type: ignore[override]
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = " ".join(str(value or "").lower().split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
            if limit is not None and len(unique) >= limit:
                break
        return unique

    def _is_health_support_retrieval_intent(self, intent=None):  # type: ignore[override]
        return False

    def _is_plant_based_diet(self, diet):  # type: ignore[override]
        return str(diet or "").lower() in {"vegetarian", "vegan"}


class _DummyProduceFocusedRetrievalQueryWorkflow(_DummyRetrievalQueryWorkflow):
    def _build_retrieval_rerank_context(self, profile, request, intent=None):  # type: ignore[override]
        return {
            "dietary_preference": profile.get("dietary_preference") or "omnivore",
            "protein_anchors": ["thit ga", "ca", "trung"],
            "carb_anchors": ["gao"],
            "produce_anchors": ["rau xanh", "trai cay"],
            "balanced_anchors": ["rau xanh"],
            "must_include": ["rau xanh", "trai cay"],
            "preferred_foods": [],
            "excluded_foods": [],
            "allergy_tags": [],
            "expected_role_tags": ["protein_anchor", "carb_anchor", "produce_support"],
            "post_workout_meal": False,
            "satiety_preference": None,
            "balanced_meal_required": False,
        }


class RetrievalSafetyRuntimeTests(unittest.TestCase):
    def test_direct_edible_allow_hints_do_not_unlock_generic_light_instruction(self) -> None:
        workflow = _DummyCandidatePoolSupportWorkflow()
        request = NutritionRecommendationRequest(
            instruction="Muon mon thanh dam va nhe bung",
            must_include=[],
            excluded_foods=[],
            meal_count=3,
            top_k=20,
        )

        allow_hints = workflow._direct_edible_raw_allow_hints(request)

        self.assertEqual(allow_hints, [])

    def test_direct_edible_allow_hints_only_keep_exact_approved_families(self) -> None:
        workflow = _DummyCandidatePoolSupportWorkflow()
        request = NutritionRecommendationRequest(
            instruction="Uu tien bun tuoi va trai cay de an truc tiep",
            must_include=["bún tươi"],
            excluded_foods=[],
            meal_count=3,
            top_k=20,
        )

        allow_hints = workflow._direct_edible_raw_allow_hints(request)

        self.assertIn("bun tuoi", allow_hints)
        self.assertIn("fruit_family", allow_hints)

    def test_direct_edible_candidate_match_is_exact_family_based(self) -> None:
        workflow = _DummyCandidatePoolSupportWorkflow()
        bun_candidate = {
            "name": "Bun tuoi",
            "safe_display_name": "Bun tuoi",
            "meal_family_key": "bun tuoi",
            "canonical_name_key": "bun tuoi",
            "consumption_state": "direct_edible_raw",
        }
        fruit_candidate = {
            "name": "Tao",
            "group_name": "Trai cay",
            "meal_family_key": "fruit_family",
            "canonical_name_key": "tao",
            "consumption_state": "direct_edible_raw",
        }
        produce_candidate = {
            "name": "Rau diep, tuoi",
            "group_name": "Rau cu",
            "meal_family_key": "greens_family",
            "canonical_name_key": "rau diep tuoi",
            "consumption_state": "direct_edible_raw",
        }

        self.assertTrue(workflow._direct_edible_raw_candidate_matches_allow_hint(bun_candidate, "bun tuoi"))
        self.assertTrue(workflow._direct_edible_raw_candidate_matches_allow_hint(fruit_candidate, "fruit_family"))
        self.assertFalse(workflow._direct_edible_raw_candidate_matches_allow_hint(produce_candidate, "fruit_family"))

    def test_retrieval_query_bundle_emits_structured_role_aware_entries(self) -> None:
        workflow = _DummyRetrievalQueryWorkflow()
        profile = {"dietary_preference": "omnivore", "allergy_tags": []}
        request = NutritionRecommendationRequest(
            instruction="Can bua an phuc hoi sau tap, uu tien ga va trung",
            must_include=["gạo", "trứng"],
            excluded_foods=["kẹo"],
            meal_count=4,
            top_k=20,
        )
        intent = NutritionIntent(goal="maintain", planning_strategy="maintenance_training_support")
        targets = {"daily_calories": 2200, "protein_g": 140, "carbs_g": 220, "fat_g": 65}

        bundle = workflow._build_retrieval_query_bundle(profile, request, targets, intent)

        self.assertLessEqual(len(bundle), 4)
        self.assertTrue(all(entry.get("query") for entry in bundle))
        self.assertTrue(all(entry.get("query_purpose") for entry in bundle))
        self.assertTrue(all(isinstance(entry.get("expected_role_tags"), list) for entry in bundle))
        self.assertIn("must_include", {entry["query_purpose"] for entry in bundle})
        self.assertIn("role_specific", {entry["query_purpose"] for entry in bundle})
        combined_query_text = " ".join(entry["query"] for entry in bundle)
        self.assertIn("fish", combined_query_text)
        self.assertIn("egg", combined_query_text)
        self.assertIn("chicken", combined_query_text)

    def test_expand_query_hint_term_for_trai_cay_uses_safe_fruit_tokens(self) -> None:
        workflow = _DummyRetrievalQueryWorkflow()

        expanded = workflow._expand_query_hint_term("trai cay")

        self.assertIn("fruit", expanded)
        self.assertIn("apple", expanded)
        self.assertIn("banana", expanded)

    def test_produce_only_must_include_builds_produce_focused_query_bundle(self) -> None:
        workflow = _DummyProduceFocusedRetrievalQueryWorkflow()
        profile = {"dietary_preference": "omnivore", "allergy_tags": []}
        request = NutritionRecommendationRequest(
            instruction="Uu tien rau xanh va trai cay",
            must_include=["rau xanh", "trai cay"],
            excluded_foods=[],
            meal_count=3,
            top_k=20,
        )
        intent = NutritionIntent(goal="maintain", planning_strategy="maintenance_health_support")
        targets = {"daily_calories": 2100, "protein_g": 80, "carbs_g": 250, "fat_g": 70}

        bundle = workflow._build_retrieval_query_bundle(profile, request, targets, intent)

        self.assertTrue(bundle)
        self.assertTrue(all("produce_support" in entry.get("expected_role_tags", []) for entry in bundle))
        combined_query_text = " ".join(entry["query"] for entry in bundle)
        self.assertIn("fruit", combined_query_text)
        self.assertIn("vegetables", combined_query_text)
        self.assertNotIn("chicken poultry protein", combined_query_text)

    def test_produce_only_request_limits_local_supplement_queries_to_produce_hints(self) -> None:
        workflow = _DummyProduceFocusedRetrievalQueryWorkflow()
        profile = {"dietary_preference": "omnivore", "allergy_tags": []}
        request = NutritionRecommendationRequest(
            instruction="Uu tien rau xanh va trai cay",
            must_include=["rau xanh", "trai cay"],
            excluded_foods=[],
            meal_count=3,
            top_k=20,
        )
        intent = NutritionIntent(goal="maintain", planning_strategy="maintenance_health_support")

        queries = workflow._build_local_supplement_queries(profile, request, intent)

        self.assertTrue(queries)
        self.assertIn("rau xanh", queries)
        self.assertIn("trai cay", queries)
        self.assertNotIn("thit ga", queries)
        self.assertNotIn("gao", queries)


if __name__ == "__main__":
    unittest.main()
