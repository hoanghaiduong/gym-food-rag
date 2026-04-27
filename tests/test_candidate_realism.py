import unittest

from app.services.nutrition.workflow.candidate_features import WorkflowCandidateFeaturesMixin
from app.services.nutrition.workflow.candidate_roles import WorkflowCandidateRolesMixin
from app.services.nutrition.workflow.meal_realism import WorkflowMealRealismMixin
from app.services.nutrition.workflow.validation_metrics import WorkflowValidationMetricsMixin


class _DummyWorkflow(
    WorkflowCandidateFeaturesMixin,
    WorkflowCandidateRolesMixin,
    WorkflowMealRealismMixin,
    WorkflowValidationMetricsMixin,
):
    pass


class CandidateRealismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _DummyWorkflow()

    def test_plain_tofu_is_not_discouraged_for_plant_based_weight_loss(self) -> None:
        candidate = {
            "name": "Dau phu, nuong",
            "group_name": "Dau va san pham che bien",
            "diet_tags": [],
            "meal_role_tags": ["protein_anchor"],
            "protein_g": 18.0,
            "carbs_g": 4.0,
            "fat_g": 16.0,
            "energy_kcal": 230.0,
        }

        realism = self.workflow._candidate_realism_profile(
            candidate,
            "lose_weight",
            dietary_preference="vegan",
        )

        self.assertNotIn("high_fat_protein_for_weight_loss", realism["discouraged_reasons"])
        self.assertIn("plant_protein_acceptable_fat", realism["preferred_reasons"])

    def test_moderate_nut_portion_is_not_seed_nut_heavy(self) -> None:
        candidate = {
            "name": "Hat macca rang",
            "group_name": "Hat va san pham che bien",
            "diet_tags": ["vegetarian", "vegan"],
            "meal_role_tags": ["fat_support"],
            "protein_g": 3.0,
            "carbs_g": 5.0,
            "fat_g": 22.0,
            "energy_kcal": 230.0,
        }

        realism = self.workflow._candidate_realism_profile(candidate, "maintain")

        self.assertNotIn("seed_nut_heavy", realism["discouraged_reasons"])

    def test_large_nut_portion_is_discouraged_for_weight_loss(self) -> None:
        candidate = {
            "name": "Hat macca rang",
            "group_name": "Hat va san pham che bien",
            "diet_tags": ["vegetarian", "vegan"],
            "meal_role_tags": ["fat_support"],
            "protein_g": 5.0,
            "carbs_g": 8.0,
            "fat_g": 35.0,
            "energy_kcal": 360.0,
        }

        realism = self.workflow._candidate_realism_profile(candidate, "lose_weight")

        self.assertIn("seed_nut_heavy", realism["discouraged_reasons"])


if __name__ == "__main__":
    unittest.main()
