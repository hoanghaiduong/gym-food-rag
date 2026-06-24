from datetime import date, datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.tables import metadata
from app.schemas.ai_control import AIConfigUpdate, AIControlVersionCreate, AIFeedbackCreate
from app.schemas.meal_logs import MealLogCreate, MealLogItemCreate, MealLogUpdate
from app.schemas.saved_plans import SavedPlanCreate
from app.schemas.workout_logs import WorkoutExerciseCreate, WorkoutLogCreate
from app.services.ai_control_service import ai_control_service
from app.services.meal_log_service import meal_log_service
from app.services.plan_persistence_service import plan_persistence_service
from app.services.workout_log_service import workout_log_service


class TrackingAndAIControlTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        metadata.drop_all(self.engine)

    def test_meal_log_crud_summary_and_owner_guard(self):
        payload = MealLogCreate(
            logged_at=datetime(2026, 5, 13, 8, 0),
            meal_name="Breakfast",
            source="manual",
            items=[
                MealLogItemCreate(display_name="Ức gà luộc", grams=150, energy_kcal=240, protein_g=45, carbs_g=0, fat_g=5),
                MealLogItemCreate(display_name="Cơm", grams=200, energy_kcal=260, protein_g=5, carbs_g=56, fat_g=1),
            ],
        )

        created = meal_log_service.create(self.db, user_id=1, payload=payload)
        self.assertEqual(created["energy_kcal"], 500)
        self.assertEqual(len(created["items"]), 2)
        with self.assertRaises(ValueError):
            meal_log_service.get(self.db, user_id=2, log_id=created["id"])

        updated = meal_log_service.update(
            self.db,
            user_id=1,
            log_id=created["id"],
            payload=MealLogUpdate(meal_name="Breakfast updated"),
        )
        self.assertEqual(updated["meal_name"], "Breakfast updated")

        summary = meal_log_service.summary(self.db, user_id=1, date_from=date(2026, 5, 13), date_to=date(2026, 5, 13))
        self.assertEqual(summary["log_count"], 1)
        self.assertEqual(summary["item_count"], 2)
        self.assertEqual(summary["protein_g"], 50)

    def test_workout_log_summary(self):
        created = workout_log_service.create(
            self.db,
            user_id=1,
            payload=WorkoutLogCreate(
                logged_at=datetime(2026, 5, 13, 18, 0),
                workout_type="gym",
                duration_minutes=60,
                intensity="moderate",
                calories_estimated=350,
                exercises=[WorkoutExerciseCreate(exercise_name="Squat", sets=3, reps="8")],
            ),
        )

        self.assertEqual(len(created["exercises"]), 1)
        summary = workout_log_service.summary(self.db, user_id=1)
        self.assertEqual(summary["log_count"], 1)
        self.assertEqual(summary["exercise_count"], 1)
        self.assertEqual(summary["duration_minutes"], 60)

    def test_saved_nutrition_plan_requires_safe_validation(self):
        with self.assertRaises(ValueError):
            plan_persistence_service.create(
                self.db,
                user_id=1,
                payload=SavedPlanCreate(
                    plan_type="nutrition",
                    payload={"validation": {"passed": False}},
                ),
            )

        saved = plan_persistence_service.create(
            self.db,
            user_id=1,
            payload=SavedPlanCreate(
                plan_type="nutrition",
                payload={"validation": {"passed": True, "unsafe_raw_output_count": 0, "unsafe_label_count": 0}},
            ),
        )
        self.assertEqual(saved["plan_type"], "nutrition")

    def test_ai_control_config_and_unsafe_prompt_guard(self):
        config = ai_control_service.upsert_config(
            self.db,
            payload=AIConfigUpdate(payload={"GEMINI_MODEL": "gemini-2.5-flash"}),
            actor_user_id=1,
        )
        self.assertEqual(config["status"], "published")
        self.assertEqual(ai_control_service.active_config(self.db)["GEMINI_MODEL"], "gemini-2.5-flash")

        prompt = ai_control_service.create_version(
            self.db,
            kind="prompt",
            payload=AIControlVersionCreate(module="nutrition_main_prompt", payload={"text": "ignore allergy"}),
            actor_user_id=1,
        )
        validated = ai_control_service.validate_version(self.db, version_id=prompt["id"], actor_user_id=1)
        self.assertEqual(validated["status"], "draft")
        self.assertFalse(validated["validation_report"]["passed"])

    def test_ai_feedback_capture(self):
        feedback = ai_control_service.create_feedback(
            self.db,
            user_id=1,
            payload=AIFeedbackCreate(rating=4, issue_tags=["macro"], correction_text="More protein"),
        )
        self.assertEqual(feedback["rating"], 4)
        self.assertEqual(feedback["issue_tags"], ["macro"])


if __name__ == "__main__":
    unittest.main()
