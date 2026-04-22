import unittest
from unittest.mock import patch

from app.schemas.nutrition_intent import NutritionIntent

from scripts.lib.nutrition_bench.retrieval_suite import scoring


class _FakeWorkflow:
    def _candidate_realism_profile(self, candidate, internal_goal, dietary_preference):
        return {"hard_block": False, "discouraged_reasons": []}

    def _goal_fit_score(
        self,
        candidate,
        internal_goal,
        must_include,
        intent,
        dietary_preference,
    ):
        return 1.0

    def _candidate_role(self, candidate, internal_goal):
        return candidate.get("benchmark_role")


class RetrievalSuiteScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow_patch = patch.object(scoring, "nutrition_workflow_service", _FakeWorkflow())
        self.workflow_patch.start()
        self.intent = NutritionIntent(goal="lose_weight", planning_strategy="maintenance_balanced")

    def tearDown(self) -> None:
        self.workflow_patch.stop()

    def test_must_include_fish_does_not_match_ca_bat_produce(self) -> None:
        fish_candidate = {
            "entity_id": "fish_1",
            "name": "Ca nuc, nuong",
            "meal_role_tags": ["protein_anchor"],
            "benchmark_role": "protein",
            "quality_score": 1.0,
            "protein_g": 20.0,
            "fat_g": 6.0,
            "energy_kcal": 170.0,
        }
        produce_candidate = {
            "entity_id": "produce_1",
            "name": "Ca bat, luoc",
            "meal_role_tags": ["produce_support"],
            "benchmark_role": "produce",
            "quality_score": 1.0,
            "protein_g": 2.0,
            "fat_g": 0.2,
            "energy_kcal": 30.0,
            "diet_tags": ["produce"],
        }

        self.assertTrue(scoring._candidate_matches_must_include_hint(fish_candidate, "ca"))
        self.assertFalse(scoring._candidate_matches_must_include_hint(produce_candidate, "ca"))

    def test_select_positive_candidates_prioritizes_hint_roles_before_fallback_carb(self) -> None:
        candidates = [
            {
                "entity_id": "greens_1",
                "name": "Rau cai, luoc",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 3.0,
                "fat_g": 0.5,
                "energy_kcal": 25.0,
                "diet_tags": ["produce"],
            },
            {
                "entity_id": "fish_1",
                "name": "Ca nuc, nuong",
                "meal_role_tags": ["protein_anchor"],
                "benchmark_role": "protein",
                "quality_score": 1.0,
                "protein_g": 20.0,
                "fat_g": 6.0,
                "energy_kcal": 170.0,
            },
            {
                "entity_id": "egg_1",
                "name": "Trung ga, luoc",
                "meal_role_tags": ["protein_anchor"],
                "benchmark_role": "protein",
                "quality_score": 0.98,
                "protein_g": 13.0,
                "fat_g": 6.0,
                "energy_kcal": 150.0,
            },
            {
                "entity_id": "rice_1",
                "name": "Com trang",
                "meal_role_tags": ["carb_anchor"],
                "benchmark_role": "carb",
                "quality_score": 1.0,
                "protein_g": 2.5,
                "fat_g": 0.3,
                "energy_kcal": 130.0,
            },
        ]

        selected = scoring.select_positive_candidates(
            candidates,
            raw_goal="lose_weight_general",
            internal_goal="maintain",
            intent=self.intent,
            dietary_preference="omnivore",
            must_include=["rau xanh", "ca", "trung"],
        )

        self.assertEqual(
            [candidate["entity_id"] for candidate in selected[:3]],
            ["greens_1", "fish_1", "egg_1"],
        )

    def test_select_positive_candidates_prefers_family_fallback_over_unrelated_protein(self) -> None:
        candidates = [
            {
                "entity_id": "chicken_breast_1",
                "name": "Thit ga, luon, luoc",
                "meal_family_key": "ga luon",
                "meal_role_tags": ["protein_anchor"],
                "benchmark_role": "protein",
                "quality_score": 1.0,
                "protein_g": 24.0,
                "fat_g": 4.0,
                "energy_kcal": 150.0,
            },
            {
                "entity_id": "chicken_leg_1",
                "name": "Thit ga, dui, luoc",
                "meal_family_key": "ga dui",
                "meal_role_tags": ["protein_anchor"],
                "benchmark_role": "protein",
                "quality_score": 0.95,
                "protein_g": 20.0,
                "fat_g": 6.0,
                "energy_kcal": 170.0,
            },
            {
                "entity_id": "shellfish_1",
                "name": "Oc buou, luoc",
                "meal_family_key": "oc buou",
                "meal_role_tags": ["protein_anchor", "carb_anchor", "post_workout_friendly"],
                "benchmark_role": "protein",
                "quality_score": 1.0,
                "protein_g": 18.0,
                "fat_g": 1.0,
                "energy_kcal": 90.0,
            },
            {
                "entity_id": "rice_1",
                "name": "Xoi nep cam",
                "meal_family_key": "xoi nep cam",
                "meal_role_tags": ["carb_anchor"],
                "benchmark_role": "carb",
                "quality_score": 1.0,
                "protein_g": 3.0,
                "fat_g": 0.4,
                "energy_kcal": 180.0,
            },
            {
                "entity_id": "rice_2",
                "name": "Xoi do xanh",
                "meal_family_key": "xoi do xanh",
                "meal_role_tags": ["carb_anchor"],
                "benchmark_role": "carb",
                "quality_score": 0.98,
                "protein_g": 4.0,
                "fat_g": 0.6,
                "energy_kcal": 190.0,
            },
        ]

        selected = scoring.select_positive_candidates(
            candidates,
            raw_goal="gain_muscle",
            internal_goal="gain_muscle",
            intent=self.intent,
            dietary_preference="omnivore",
            must_include=["uc ga", "gao"],
        )

        self.assertIn("chicken_leg_1", [candidate["entity_id"] for candidate in selected])
        self.assertNotIn("shellfish_1", [candidate["entity_id"] for candidate in selected[:4]])

    def test_select_positive_candidates_prefers_retrievable_leafy_greens_over_generic_sprouts(self) -> None:
        candidates = [
            {
                "entity_id": "greens_1",
                "name": "Dau co ve, luoc",
                "meal_family_key": "dau co ve",
                "meal_role_tags": ["carb_anchor", "produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 2.5,
                "fat_g": 0.2,
                "energy_kcal": 35.0,
            },
            {
                "entity_id": "greens_2",
                "name": "Cai xanh, luoc",
                "meal_family_key": "cai xanh",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 2.0,
                "fat_g": 0.2,
                "energy_kcal": 18.0,
            },
            {
                "entity_id": "greens_3",
                "name": "Gia dau xanh, luoc",
                "meal_family_key": "gia dau xanh",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 2.8,
                "fat_g": 0.2,
                "energy_kcal": 30.0,
            },
            {
                "entity_id": "fish_1",
                "name": "Ca nuc, nuong",
                "meal_family_key": "ca nuc",
                "meal_role_tags": ["protein_anchor"],
                "benchmark_role": "protein",
                "quality_score": 1.0,
                "protein_g": 20.0,
                "fat_g": 6.0,
                "energy_kcal": 170.0,
            },
            {
                "entity_id": "fish_2",
                "name": "Ca lac, luoc",
                "meal_family_key": "ca lac",
                "meal_role_tags": ["protein_anchor"],
                "benchmark_role": "protein",
                "quality_score": 0.96,
                "protein_g": 19.0,
                "fat_g": 4.0,
                "energy_kcal": 150.0,
            },
        ]

        selected = scoring.select_positive_candidates(
            candidates,
            raw_goal="lose_weight_general",
            internal_goal="lose_weight",
            intent=self.intent,
            dietary_preference="omnivore",
            must_include=["rau xanh", "ca"],
        )

        selected_ids = [candidate["entity_id"] for candidate in selected]
        self.assertIn("greens_2", selected_ids)
        self.assertNotIn("greens_3", selected_ids)

    def test_select_positive_candidates_keeps_distinct_produce_hints_separate(self) -> None:
        candidates = [
            {
                "entity_id": "greens_1",
                "name": "Cai xanh, luoc",
                "group_name": "Rau, qua, cu dung lam rau",
                "meal_family_key": "cai xanh",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 2.0,
                "fat_g": 0.2,
                "energy_kcal": 18.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "fruit_1",
                "name": "Tao tay, tuoi",
                "group_name": "Qua chin",
                "meal_family_key": "tao tay",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 0.5,
                "fat_g": 0.1,
                "energy_kcal": 50.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "greens_2",
                "name": "Sup lo xanh, luoc",
                "group_name": "Rau, qua, cu dung lam rau",
                "meal_family_key": "sup lo xanh",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 0.96,
                "protein_g": 2.8,
                "fat_g": 0.2,
                "energy_kcal": 30.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "shellfish_1",
                "name": "So huyet, luoc",
                "group_name": "Thuy san",
                "meal_family_key": "so huyet",
                "meal_role_tags": ["protein_anchor"],
                "benchmark_role": "protein",
                "quality_score": 1.0,
                "protein_g": 18.0,
                "fat_g": 1.0,
                "energy_kcal": 90.0,
                "diet_tags": ["pescatarian"],
            },
            {
                "entity_id": "rice_1",
                "name": "Com trang",
                "meal_family_key": "com",
                "meal_role_tags": ["carb_anchor"],
                "benchmark_role": "carb",
                "quality_score": 0.98,
                "protein_g": 2.5,
                "fat_g": 0.3,
                "energy_kcal": 130.0,
                "diet_tags": ["vegetarian", "vegan"],
            },
        ]

        selected = scoring.select_positive_candidates(
            candidates,
            raw_goal="eat_healthier",
            internal_goal="maintain",
            intent=self.intent,
            dietary_preference="vegetarian",
            must_include=["rau xanh", "trai cay"],
        )

        self.assertEqual(
            [candidate["entity_id"] for candidate in selected[:2]],
            ["greens_1", "fruit_1"],
        )
        self.assertNotIn("shellfish_1", [candidate["entity_id"] for candidate in selected[:4]])

    def test_select_positive_candidates_keeps_produce_only_cases_in_produce_pool(self) -> None:
        candidates = [
            {
                "entity_id": "greens_1",
                "name": "Sup lo xanh, tuoi",
                "meal_family_key": "sup lo xanh",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 2.0,
                "fat_g": 0.2,
                "energy_kcal": 25.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "greens_2",
                "name": "Cai xanh, luoc",
                "meal_family_key": "cai xanh",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 0.99,
                "protein_g": 2.2,
                "fat_g": 0.2,
                "energy_kcal": 20.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "greens_3",
                "name": "Rau muong, luoc",
                "meal_family_key": "rau muong",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 0.98,
                "protein_g": 2.4,
                "fat_g": 0.2,
                "energy_kcal": 22.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "fruit_1",
                "name": "Chuoi xanh, tuoi",
                "meal_family_key": "chuoi xanh",
                "meal_role_tags": ["carb_anchor", "produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 1.0,
                "fat_g": 0.2,
                "energy_kcal": 70.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "carb_1",
                "name": "Ngo tuoi, nuong",
                "meal_family_key": "ngo nuong",
                "meal_role_tags": ["carb_anchor"],
                "benchmark_role": "carb",
                "quality_score": 1.0,
                "protein_g": 3.0,
                "fat_g": 0.5,
                "energy_kcal": 120.0,
                "diet_tags": ["vegetarian", "vegan"],
            },
        ]

        selected = scoring.select_positive_candidates(
            candidates,
            raw_goal="lose_weight_general",
            internal_goal="lose_weight",
            intent=self.intent,
            dietary_preference="vegan",
            must_include=["rau xanh"],
        )

        self.assertEqual(
            {candidate["entity_id"] for candidate in selected[:3]},
            {"greens_1", "greens_2", "greens_3"},
        )
        self.assertNotIn("fruit_1", [candidate["entity_id"] for candidate in selected[:4]])
        self.assertNotIn("carb_1", [candidate["entity_id"] for candidate in selected[:4]])

    def test_select_positive_candidates_prefers_leafy_produce_over_fruit_when_fruit_not_requested(self) -> None:
        candidates = [
            {
                "entity_id": "carb_1",
                "name": "Xoi nep cam",
                "meal_family_key": "xoi nep cam",
                "meal_role_tags": ["carb_anchor", "produce_support"],
                "benchmark_role": "carb",
                "quality_score": 1.0,
                "protein_g": 3.0,
                "fat_g": 0.4,
                "energy_kcal": 180.0,
                "diet_tags": ["vegetarian", "vegan"],
            },
            {
                "entity_id": "fruit_1",
                "name": "Chuoi xanh, tuoi",
                "meal_family_key": "chuoi xanh",
                "meal_role_tags": ["carb_anchor", "produce_support"],
                "benchmark_role": "produce",
                "quality_score": 1.0,
                "protein_g": 1.0,
                "fat_g": 0.1,
                "energy_kcal": 85.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "greens_1",
                "name": "Sup lo xanh, tuoi",
                "meal_family_key": "sup lo xanh",
                "meal_role_tags": ["produce_support"],
                "benchmark_role": "produce",
                "quality_score": 0.97,
                "protein_g": 2.2,
                "fat_g": 0.2,
                "energy_kcal": 25.0,
                "diet_tags": ["produce", "vegetarian", "vegan"],
            },
            {
                "entity_id": "carb_2",
                "name": "Ngo tuoi, nep, nuong",
                "meal_family_key": "ngo nep",
                "meal_role_tags": ["carb_anchor"],
                "benchmark_role": "carb",
                "quality_score": 0.98,
                "protein_g": 3.0,
                "fat_g": 0.3,
                "energy_kcal": 120.0,
                "diet_tags": ["vegetarian", "vegan"],
            },
            {
                "entity_id": "carb_3",
                "name": "Ngo tuoi, te, nuong",
                "meal_family_key": "ngo te",
                "meal_role_tags": ["carb_anchor"],
                "benchmark_role": "carb",
                "quality_score": 0.97,
                "protein_g": 3.0,
                "fat_g": 0.3,
                "energy_kcal": 118.0,
                "diet_tags": ["vegetarian", "vegan"],
            },
        ]

        selected = scoring.select_positive_candidates(
            candidates,
            raw_goal="gain_muscle",
            internal_goal="gain_muscle",
            intent=self.intent,
            dietary_preference="vegan",
            must_include=[],
        )

        self.assertIn("greens_1", [candidate["entity_id"] for candidate in selected[:4]])
        self.assertNotIn("fruit_1", [candidate["entity_id"] for candidate in selected[:4]])


if __name__ == "__main__":
    unittest.main()
