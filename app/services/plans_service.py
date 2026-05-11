from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo


ProfileBuilder = Callable[[dict[str, Any]], dict[str, Any]]


class PlansService:
    WEEKDAY_SLUGS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    WEEKDAY_LABELS = (
        "Thứ Hai",
        "Thứ Ba",
        "Thứ Tư",
        "Thứ Năm",
        "Thứ Sáu",
        "Thứ Bảy",
        "Chủ Nhật",
    )
    GOAL_LABELS = {
        "gain_muscle": "Tăng cơ",
        "gain-muscle": "Tăng cơ",
        "muscle_gain": "Tăng cơ",
        "lose_weight": "Giảm mỡ",
        "lose-weight": "Giảm mỡ",
        "lose_fat": "Giảm mỡ",
        "lose-fat": "Giảm mỡ",
        "fat_loss": "Giảm mỡ",
        "lose_weight_general": "Giảm mỡ",
        "maintain": "Duy trì",
    }

    def __init__(self, profile_builder: Optional[ProfileBuilder] = None):
        self._profile_builder = profile_builder

    def build_weekly(
        self,
        current_user: dict[str, Any],
        *,
        week_start: Optional[date] = None,
        today: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        current_day = today or self._today()
        start_day = week_start or self._start_of_week(current_day)
        profile = self._build_profile(current_user)
        subtitle = self._build_subtitle(profile)

        items = []
        for offset in range(7):
            item_date = start_day + timedelta(days=offset)
            items.append(
                {
                    "id": f"{self.WEEKDAY_SLUGS[item_date.weekday()]}-{item_date.isoformat()}",
                    "day_label": f"{self.WEEKDAY_LABELS[item_date.weekday()]} • {item_date:%d/%m}",
                    "title": self._build_title(profile),
                    "subtitle": subtitle,
                    "status": self._resolve_status(item_date, current_day),
                }
            )
        return items

    def build_monthly(
        self,
        current_user: dict[str, Any],
        *,
        year: int,
        month: int,
        today: Optional[date] = None,
    ) -> dict[str, Any]:
        current_day = today or self._today()
        days_in_month = calendar.monthrange(year, month)[1]
        profile = self._build_profile(current_user)
        profile_completed = bool(profile.get("is_profile_completed"))
        selected_date = self._selected_date(year, month, current_day)

        return {
            "year": year,
            "month": month,
            "days": [
                {
                    "day": day_number,
                    "has_completed_workout": False,
                    "has_planned_workout": False,
                    "is_today": self._is_today(year, month, day_number, current_day),
                }
                for day_number in range(1, days_in_month + 1)
            ],
            "monthly_progress": {
                "workout_completed": 0,
                "workout_target": self._workout_target(profile, days_in_month) if profile_completed else 0,
                "nutrition_completed": 0,
                "nutrition_target": days_in_month if profile_completed else 0,
            },
            "selected_day": {
                "date": selected_date,
                "title": "Chưa có lịch tập",
                "subtitle": "Chưa có kế hoạch cụ thể",
                "calories": 0.0,
            },
        }

    def _build_profile(self, current_user: dict[str, Any]) -> dict[str, Any]:
        if self._profile_builder:
            return self._profile_builder(current_user)
        from app.services.nutrition_workflow_service import nutrition_workflow_service

        return nutrition_workflow_service.build_profile(current_user)

    def _today(self) -> date:
        try:
            return datetime.now(ZoneInfo("Asia/Bangkok")).date()
        except Exception:
            return date.today()

    def _start_of_week(self, value: date) -> date:
        return value - timedelta(days=value.weekday())

    def _build_title(self, profile: dict[str, Any]) -> str:
        if profile.get("is_profile_completed"):
            return "Kế hoạch tuần này"
        return "Cập nhật kế hoạch"

    def _build_subtitle(self, profile: dict[str, Any]) -> str:
        goal = self._resolve_goal_label(profile)
        calories = self._safe_int(profile.get("daily_calories"))
        minutes = self._safe_int(profile.get("workout_minutes"))
        parts = [goal]
        if calories:
            parts.append(f"{calories} kcal")
        if minutes:
            parts.append(f"{minutes} phút")
        if len(parts) == 1 and parts[0] == "Chưa có mục tiêu":
            return "Chưa có lịch tập cụ thể"
        return " • ".join(parts)

    def _resolve_goal_label(self, profile: dict[str, Any]) -> str:
        raw_goal = str(profile.get("goal_normalized_internal") or profile.get("target_goal") or "")
        normalized_goal = raw_goal.replace("-", "_")
        return self.GOAL_LABELS.get(raw_goal) or self.GOAL_LABELS.get(normalized_goal) or "Chưa có mục tiêu"

    def _resolve_status(self, item_date: date, today: date) -> str:
        if item_date < today:
            return "completed"
        if item_date == today:
            return "active"
        return "upcoming"

    def _selected_date(self, year: int, month: int, today: date) -> date:
        if today.year == year and today.month == month:
            return today
        return date(year, month, 1)

    def _is_today(self, year: int, month: int, day_number: int, today: date) -> bool:
        return today.year == year and today.month == month and today.day == day_number

    def _workout_target(self, profile: dict[str, Any], days_in_month: int) -> int:
        workouts_per_week = self._safe_int(profile.get("workouts_per_week"))
        if not workouts_per_week:
            return 0
        return round(workouts_per_week * days_in_month / 7)

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


plans_service = PlansService()
