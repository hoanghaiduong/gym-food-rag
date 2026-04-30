import unittest

from app.services.nutrition.workflow.candidate_roles import WorkflowCandidateRolesMixin
from app.services.nutrition.workflow.meal_realism import WorkflowMealRealismMixin


class _DummyWorkflow(WorkflowMealRealismMixin, WorkflowCandidateRolesMixin):
    pass


class CandidateRolesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _DummyWorkflow()

    def test_carb_dominant_dual_anchor_is_classified_as_carb(self) -> None:
        candidate = {
            "name": "Nui, luoc",
            "group_name": "Ngu coc va san pham che bien",
            "meal_role_tags": ["protein_anchor", "carb_anchor", "produce_support"],
            "diet_tags": [],
            "protein_g": 13.0,
            "carbs_g": 75.0,
            "fat_g": 1.5,
            "energy_kcal": 371.0,
        }

        self.assertEqual(self.workflow._candidate_role(candidate, "gain_muscle"), "carb")

    def test_resolved_food_name_is_used_when_name_is_missing(self) -> None:
        candidate = {
            "food_name": "Xoi trung op la",
            "group_name": "Cac mon xoi, che",
            "meal_role_tags": ["protein_anchor", "carb_anchor", "main_meal"],
            "diet_tags": [],
            "protein_g": 8.3,
            "carbs_g": 33.5,
            "fat_g": 8.5,
            "energy_kcal": 243.9,
        }

        self.assertEqual(self.workflow._candidate_role(candidate, "maintain"), "carb")

    def test_real_fish_anchor_stays_protein(self) -> None:
        candidate = {
            "name": "Ca nuc, nuong",
            "group_name": "Thuy san va san pham che bien",
            "meal_role_tags": ["protein_anchor", "post_workout_friendly"],
            "diet_tags": ["high_protein"],
            "protein_g": 25.0,
            "carbs_g": 0.0,
            "fat_g": 4.0,
            "energy_kcal": 138.0,
        }

        self.assertEqual(self.workflow._candidate_role(candidate, "gain_muscle"), "protein")


if __name__ == "__main__":
    unittest.main()
