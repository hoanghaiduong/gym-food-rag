import unittest

from app.schemas.nutrition import NutritionRecommendationRequest
from app.services.nutrition.intent.service import nutrition_intent_service


class NutritionIntentExclusionTests(unittest.TestCase):
    def test_no_seafood_instruction_becomes_hard_exclusion(self) -> None:
        profile = {"target_goal": "gain_muscle", "dietary_preference": "omnivore", "allergy_tags": []}
        request = NutritionRecommendationRequest(
            instruction="toi muon tang co, khong an hai san, uu tien bua don gian",
            meal_count=3,
            top_k=12,
        )

        intent = nutrition_intent_service._build_heuristic_intent(profile, request)
        effective_request = nutrition_intent_service.apply_to_request(request, intent)

        self.assertIn("hai san", intent.hard_constraints.must_avoid)
        self.assertIn("hai san", effective_request.excluded_foods)

    def test_no_fish_instruction_becomes_fish_exclusion(self) -> None:
        profile = {"target_goal": "maintain", "dietary_preference": "omnivore", "allergy_tags": []}
        request = NutritionRecommendationRequest(
            instruction="khong an ca, uu tien mon de lam",
            meal_count=3,
            top_k=12,
        )

        intent = nutrition_intent_service._build_heuristic_intent(profile, request)

        self.assertIn("ca", intent.hard_constraints.must_avoid)


if __name__ == "__main__":
    unittest.main()
