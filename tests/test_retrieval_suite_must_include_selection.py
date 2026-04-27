import unittest
from unittest.mock import patch

from scripts.lib.nutrition_bench.retrieval_suite.assembly import build_query
from scripts.lib.nutrition_bench.retrieval_suite.must_include_selection import (
    select_benchmark_must_include,
)


class RetrievalSuiteMustIncludeSelectionTests(unittest.TestCase):
    def test_selection_skips_unavailable_duplicate_role_and_keeps_available_carb(self) -> None:
        candidates = (
            {
                "entity_id": "chicken_1",
                "name": "Thit ga, luon, luoc",
                "meal_role_tags": ["protein_anchor"],
            },
            {
                "entity_id": "rice_1",
                "name": "Com trang",
                "meal_role_tags": ["carb_anchor"],
            },
        )

        with patch(
            "scripts.lib.nutrition_bench.retrieval_suite.must_include_selection._cached_candidate_pool",
            return_value=candidates,
        ):
            result = select_benchmark_must_include(
                dietary_preference="omnivore",
                allergy_tags=[],
                excluded_foods=[],
                seed_hints=["uc ga", "trung", "gao"],
                target_count=2,
            )

        self.assertEqual(list(result.selected_hints), ["uc ga", "gao"])
        self.assertIn("trung", result.unavailable_hints)

    def test_selection_requires_strict_fish_family_not_shellfish(self) -> None:
        candidates = (
            {
                "entity_id": "greens_1",
                "name": "Rau cai, luoc",
                "group_name": "Rau",
                "meal_role_tags": ["produce_support"],
            },
            {
                "entity_id": "shellfish_1",
                "name": "So huyet, luoc",
                "name_en": "Blood cockle, boiled",
                "meal_role_tags": ["protein_anchor"],
            },
            {
                "entity_id": "fish_1",
                "name": "Ca nuc, nuong",
                "name_en": "Fish, grilled",
                "meal_role_tags": ["protein_anchor"],
            },
        )

        with patch(
            "scripts.lib.nutrition_bench.retrieval_suite.must_include_selection._cached_candidate_pool",
            return_value=candidates,
        ):
            result = select_benchmark_must_include(
                dietary_preference="omnivore",
                allergy_tags=[],
                excluded_foods=[],
                seed_hints=["rau xanh", "trung", "ca"],
                target_count=2,
            )

        self.assertEqual(list(result.selected_hints), ["rau xanh", "ca"])
        self.assertIn("trung", result.unavailable_hints)

    def test_build_query_handles_single_must_include_hint(self) -> None:
        query = build_query(
            goal_text="Muốn ăn khỏe hơn",
            diet="omnivore",
            style="easy",
            allergy_phrase=None,
            must_include=["rau xanh"],
        )

        self.assertIn("Ưu tiên rau xanh", query)

    def test_selection_keeps_seed_order_for_distinct_produce_hints(self) -> None:
        candidates = (
            {
                "entity_id": "greens_1",
                "name": "Cai xanh, luoc",
                "group_name": "Rau",
                "meal_role_tags": ["produce_support"],
            },
            {
                "entity_id": "fruit_1",
                "name": "Tao tay, tuoi",
                "group_name": "Qua chin",
                "meal_role_tags": ["produce_support"],
            },
            {
                "entity_id": "rice_1",
                "name": "Com trang",
                "meal_role_tags": ["carb_anchor"],
            },
        )

        with patch(
            "scripts.lib.nutrition_bench.retrieval_suite.must_include_selection._cached_candidate_pool",
            return_value=candidates,
        ):
            result = select_benchmark_must_include(
                dietary_preference="omnivore",
                allergy_tags=[],
                excluded_foods=[],
                seed_hints=["rau xanh", "trai cay", "gao"],
                target_count=2,
            )

        self.assertEqual(list(result.selected_hints), ["rau xanh", "trai cay"])
        self.assertEqual(list(result.deferred_hints), [])

    def test_selection_adds_role_diverse_fallback_when_seed_hints_are_unavailable(self) -> None:
        candidates = (
            {
                "entity_id": "greens_1",
                "name": "Sup lo xanh",
                "group_name": "Rau",
                "meal_role_tags": ["produce_support"],
            },
            {
                "entity_id": "rice_1",
                "name": "Com trang",
                "meal_role_tags": ["carb_anchor"],
            },
        )

        with patch(
            "scripts.lib.nutrition_bench.retrieval_suite.must_include_selection._cached_candidate_pool",
            return_value=candidates,
        ):
            result = select_benchmark_must_include(
                dietary_preference="vegan",
                allergy_tags=["shellfish"],
                excluded_foods=["tom", "cua", "oc"],
                seed_hints=["rau xanh", "dau xanh", "yen mach"],
                target_count=2,
            )

        self.assertEqual(list(result.selected_hints), ["rau xanh", "gao"])
        self.assertEqual(list(result.fallback_hints), ["gao"])
        self.assertIn("dau xanh", result.unavailable_hints)


if __name__ == "__main__":
    unittest.main()
