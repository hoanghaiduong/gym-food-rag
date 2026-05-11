from __future__ import annotations

from typing import Any, Optional

from app.services.nutrition_service import NutritionService
from app.services.nutrition_workflow_service import nutrition_workflow_service


class DashboardOverviewService:
    GOAL_LABELS = {
        "gain_muscle": "Tăng cơ",
        "lose_weight": "Giảm mỡ",
        "maintain": "Duy trì",
    }

    def build_overview(self, current_user: dict[str, Any]) -> dict[str, Any]:
        profile = nutrition_workflow_service.build_profile(current_user)
        profile_completed = bool(profile.get("is_profile_completed"))
        targets = self._calculate_targets(profile) if profile_completed else None

        calories_consumed = 0.0
        calories_target = self._round_or_zero((targets or {}).get("calories"))
        return {
            "greeting_name": self._resolve_greeting_name(profile),
            "goal_label": self._resolve_goal_label(profile),
            "weekly_progress": 0.0,
            "calories_consumed": calories_consumed,
            "calories_target": calories_target,
            "calories_remaining": max(calories_target - calories_consumed, 0.0),
            "macros": {
                "protein_g": self._round_or_zero((targets or {}).get("protein")),
                "carbs_g": self._round_or_zero((targets or {}).get("carbs")),
                "fat_g": self._round_or_zero((targets or {}).get("fat")),
            },
            "timeline": [],
            "bmi": self._calculate_bmi(profile),
            "weight_kg": self._safe_float(profile.get("weight")),
            "bmr": self._calculate_bmr(profile),
            "trend_points": [],
            "recent_plans": [],
            "profile_completed": profile_completed,
        }

    def _calculate_targets(self, profile: dict[str, Any]) -> dict[str, float] | None:
        bmr = self._calculate_bmr(profile)
        if bmr is None:
            return None

        activity_multiplier = self._activity_multiplier(profile.get("activity_level"))
        tdee = bmr * activity_multiplier
        return NutritionService.get_macro_targets(
            tdee,
            str(profile.get("goal_normalized_internal") or profile.get("target_goal") or "maintain"),
            dietary_preference=str(profile.get("dietary_preference") or "omnivore"),
            weight=self._safe_float(profile.get("weight")),
            strategy=profile.get("planning_strategy"),
        )

    def _resolve_greeting_name(self, profile: dict[str, Any]) -> str:
        full_name = str(profile.get("full_name") or "").strip()
        if full_name:
            return full_name
        username = str(profile.get("username") or "").strip()
        return username or "Bạn"

    def _resolve_goal_label(self, profile: dict[str, Any]) -> str:
        goal = profile.get("goal_normalized_internal") or profile.get("target_goal")
        return self.GOAL_LABELS.get(str(goal or ""), "Cập nhật hồ sơ")

    def _calculate_bmi(self, profile: dict[str, Any]) -> Optional[float]:
        weight = self._safe_float(profile.get("weight"))
        height_cm = self._safe_float(profile.get("height"))
        if not weight or not height_cm:
            return None
        height_m = height_cm / 100.0
        if height_m <= 0:
            return None
        return round(weight / (height_m * height_m), 1)

    def _calculate_bmr(self, profile: dict[str, Any]) -> Optional[float]:
        age = self._safe_int(profile.get("age"))
        gender = str(profile.get("gender") or "").lower()
        weight = self._safe_float(profile.get("weight"))
        height = self._safe_float(profile.get("height"))
        if not age or not gender or not weight or not height:
            return None
        if gender == "male":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        elif gender == "female":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        else:
            return None
        return round(bmr, 1)

    def _activity_multiplier(self, activity_level: Any) -> float:
        multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }
        return multipliers.get(str(activity_level or "").lower(), 1.2)

    def _round_or_zero(self, value: Any) -> float:
        parsed = self._safe_float(value)
        return round(parsed, 1) if parsed is not None else 0.0

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


dashboard_overview_service = DashboardOverviewService()
