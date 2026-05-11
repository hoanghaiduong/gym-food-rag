from datetime import date
import unittest

from app.services.plans_service import PlansService


def complete_profile_builder(_current_user):
    return {
        "username": "demo",
        "full_name": "Demo User",
        "target_goal": "lose_weight",
        "goal_normalized_internal": "lose_weight",
        "is_profile_completed": True,
        "daily_calories": 2200,
        "workout_minutes": 60,
        "workouts_per_week": 4,
    }


def incomplete_profile_builder(_current_user):
    return {
        "username": "demo",
        "full_name": "",
        "target_goal": None,
        "goal_normalized_internal": None,
        "is_profile_completed": False,
        "workouts_per_week": None,
    }


def transition_goal_profile_builder(current_user):
    profile = complete_profile_builder(current_user)
    profile["target_goal"] = "lose-fat"
    profile["goal_normalized_internal"] = "lose-fat"
    return profile


class PlansServiceTests(unittest.TestCase):
    def test_weekly_plan_generates_seven_days_with_expected_statuses(self):
        service = PlansService(profile_builder=complete_profile_builder)
        items = service.build_weekly(
            {"id": 1, "username": "demo"},
            week_start=date(2026, 5, 4),
            today=date(2026, 5, 6),
        )

        self.assertEqual(len(items), 7)
        self.assertEqual(items[0]["id"], "mon-2026-05-04")
        self.assertIn("04/05", items[0]["day_label"])
        self.assertEqual(items[0]["status"], "completed")
        self.assertEqual(items[2]["id"], "wed-2026-05-06")
        self.assertEqual(items[2]["status"], "active")
        self.assertEqual(items[6]["status"], "upcoming")
        self.assertEqual(items[2]["subtitle"], "Giảm mỡ • 2200 kcal • 60 phút")

    def test_weekly_plan_accepts_transition_goal_aliases(self):
        service = PlansService(profile_builder=transition_goal_profile_builder)
        items = service.build_weekly(
            {"id": 1, "username": "demo"},
            week_start=date(2026, 5, 4),
            today=date(2026, 5, 6),
        )

        self.assertEqual(items[2]["subtitle"], "Giảm mỡ • 2200 kcal • 60 phút")

    def test_weekly_plan_defaults_to_current_week_start(self):
        service = PlansService(profile_builder=incomplete_profile_builder)
        items = service.build_weekly(
            {"id": 1, "username": "demo"},
            today=date(2026, 5, 6),
        )

        self.assertEqual(items[0]["id"], "mon-2026-05-04")
        self.assertEqual(items[0]["title"], "Cập nhật kế hoạch")
        self.assertEqual(items[0]["subtitle"], "Chưa có lịch tập cụ thể")

    def test_monthly_plan_generates_calendar_and_profile_targets(self):
        service = PlansService(profile_builder=complete_profile_builder)
        payload = service.build_monthly(
            {"id": 1, "username": "demo"},
            year=2026,
            month=5,
            today=date(2026, 5, 6),
        )

        self.assertEqual(payload["year"], 2026)
        self.assertEqual(payload["month"], 5)
        self.assertEqual(len(payload["days"]), 31)
        self.assertTrue(payload["days"][5]["is_today"])
        self.assertFalse(payload["days"][5]["has_completed_workout"])
        self.assertFalse(payload["days"][5]["has_planned_workout"])
        self.assertEqual(payload["monthly_progress"]["workout_completed"], 0)
        self.assertEqual(payload["monthly_progress"]["workout_target"], 18)
        self.assertEqual(payload["monthly_progress"]["nutrition_target"], 31)
        self.assertEqual(payload["selected_day"]["date"], date(2026, 5, 6))

    def test_monthly_plan_returns_safe_defaults_for_incomplete_profile(self):
        service = PlansService(profile_builder=incomplete_profile_builder)
        payload = service.build_monthly(
            {"id": 1, "username": "demo"},
            year=2026,
            month=2,
            today=date(2026, 5, 6),
        )

        self.assertEqual(len(payload["days"]), 28)
        self.assertFalse(any(day["is_today"] for day in payload["days"]))
        self.assertEqual(payload["monthly_progress"]["workout_target"], 0)
        self.assertEqual(payload["monthly_progress"]["nutrition_target"], 0)
        self.assertEqual(payload["selected_day"]["date"], date(2026, 2, 1))
        self.assertEqual(payload["selected_day"]["calories"], 0.0)


if __name__ == "__main__":
    unittest.main()
