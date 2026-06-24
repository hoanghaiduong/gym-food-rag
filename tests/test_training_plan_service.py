import unittest

from app.schemas.training import TrainingRecommendationRequest
from app.services.training_plan_service import TrainingPlanService


def complete_profile(_current_user):
    return {
        "user_id": 1,
        "username": "demo",
        "target_goal": "gain_muscle",
        "goal_normalized_internal": "gain_muscle",
        "activity_level": "active",
        "workouts_per_week": 4,
        "workout_minutes": 60,
        "training_types": "gym,calisthenics",
        "medical_conditions": "",
        "is_profile_completed": True,
    }


def limited_profile(_current_user):
    profile = complete_profile(_current_user)
    profile["medical_conditions"] = "dau goi"
    profile["is_profile_completed"] = False
    return profile


class TrainingPlanServiceTests(unittest.TestCase):
    def test_builds_training_plan_from_profile_defaults(self):
        service = TrainingPlanService(profile_builder=complete_profile)

        result = service.build_recommendation(
            {"id": 1, "username": "demo"},
            TrainingRecommendationRequest(),
        )

        self.assertEqual(result["engine"]["decision_engine"], "TrainingPlanService")
        self.assertEqual(result["goal"], "gain_muscle")
        self.assertEqual(result["weekly_frequency"], 4)
        self.assertEqual(result["session_minutes"], 60)
        self.assertEqual(len(result["schedule"]), 4)
        self.assertTrue(result["validation"]["passed"])
        self.assertIn("protein", " ".join(result["nutrition_alignment"]).lower())

    def test_request_overrides_profile_goal_and_frequency(self):
        service = TrainingPlanService(profile_builder=complete_profile)

        result = service.build_recommendation(
            {"id": 1, "username": "demo"},
            TrainingRecommendationRequest(
                goal="lose_weight",
                workouts_per_week=2,
                workout_minutes=30,
                training_types=["cardio"],
            ),
        )

        self.assertEqual(result["goal"], "lose_weight")
        self.assertEqual(result["weekly_frequency"], 2)
        self.assertEqual(result["session_minutes"], 30)
        self.assertIn("cardio", result["profile_summary"]["training_types"])

    def test_medical_limitations_lower_intensity_and_add_warning(self):
        service = TrainingPlanService(profile_builder=limited_profile)

        result = service.build_recommendation(
            {"id": 1, "username": "demo"},
            TrainingRecommendationRequest(limitations=["dau lung"]),
        )

        self.assertEqual(result["intensity"], "low")
        self.assertTrue(result["validation"]["passed"])
        codes = {issue["code"] for issue in result["validation"]["issues"]}
        self.assertIn("profile_incomplete", codes)
        self.assertIn("medical_or_mobility_limitations_present", codes)
        self.assertTrue(any("y khoa" in note for note in result["safety_notes"]))

    def test_options_contract_contains_frontend_choices(self):
        service = TrainingPlanService(profile_builder=complete_profile)
        options = service.build_options()

        self.assertIn("goals", options)
        self.assertIn("experience_levels", options)
        self.assertIn("training_types", options)
        self.assertIn("equipment", options)


if __name__ == "__main__":
    unittest.main()
