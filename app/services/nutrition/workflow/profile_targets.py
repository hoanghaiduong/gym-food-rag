from __future__ import annotations

from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize
from app.services.nutrition_service import NutritionService

from .models import WorkflowTargets
from .constants import (
    ACTIVITY_MAP,
    ALLERGY_MAP,
    DIETARY_MAP,
    GENDER_MAP,
    GOAL_MAP,
    MEAL_TEMPLATES,
    STRATEGY_TO_GOAL_FAMILY,
)


class WorkflowProfileTargetsMixin:
    _PROFILE_COMPLETION_REQUIRED_FIELDS = (
        "target_goal",
        "age",
        "gender",
        "height",
        "weight",
        "activity_level",
    )
    _LIST_PROFILE_FIELDS = {
        "training_types",
        "disliked_foods",
        "favorite_meals",
        "avoid_meals",
        "medical_conditions",
    }
    _DEFAULT_RAW_SEMANTIC_BY_GOAL = {
        "gain_muscle": "gain_muscle",
        "lose_weight": "fat_loss",
        "maintain": "maintain",
    }
    _DEFAULT_PLANNING_STRATEGY_BY_GOAL = {
        "gain_muscle": "surplus_high_protein",
        "lose_weight": "deficit_high_satiety",
        "maintain": "maintenance_balanced",
    }

    def normalize_profile_update(self, update_data: dict[str, Any]) -> dict[str, Any]:
        normalized = {}
        for field, value in update_data.items():
            if value is None:
                continue
            if field == "gender":
                normalized[field] = self._normalize_gender(value)
            elif field == "activity_level":
                normalized[field] = self._normalize_activity_level(value)
            elif field == "dietary_preference":
                normalized[field] = self._normalize_dietary_preference(value)
            elif field == "target_goal":
                normalized[field] = self._normalize_goal(value)
            elif field == "allergies":
                normalized[field] = ", ".join(self._normalize_allergies(value))
            elif field in self._LIST_PROFILE_FIELDS:
                normalized[field] = self._normalize_text_list(value)
            else:
                normalized[field] = value
        return normalized

    def build_profile(self, current_user: dict[str, Any]) -> dict[str, Any]:
        target_goal = self._normalize_goal(current_user.get("target_goal"))
        profile = {
            "user_id": current_user["id"],
            "username": current_user["username"],
            "full_name": current_user.get("full_name"),
            "phone": current_user.get("phone"),
            "avatar_url": current_user.get("avatar_url"),
            "age": current_user.get("age"),
            "gender": self._normalize_gender(current_user.get("gender")),
            "weight": current_user.get("weight"),
            "height": current_user.get("height"),
            "activity_level": self._normalize_activity_level(current_user.get("activity_level")),
            "workouts_per_week": current_user.get("workouts_per_week"),
            "workout_minutes": current_user.get("workout_minutes"),
            "training_types": current_user.get("training_types"),
            "dietary_preference": self._normalize_dietary_preference(current_user.get("dietary_preference")),
            "allergies": current_user.get("allergies"),
            "disliked_foods": current_user.get("disliked_foods"),
            "favorite_meals": current_user.get("favorite_meals"),
            "avoid_meals": current_user.get("avoid_meals"),
            "medical_conditions": current_user.get("medical_conditions"),
            "target_goal": target_goal,
            "allergy_tags": self._normalize_allergies(current_user.get("allergies")),
        }
        return self.ensure_profile_contract(profile)

    def ensure_profile_contract(self, profile: dict[str, Any]) -> dict[str, Any]:
        profile = dict(profile)
        target_goal = self._normalize_goal(profile.get("target_goal"))
        normalized_goal = self._normalize_goal(profile.get("goal_normalized_internal")) or target_goal

        profile["target_goal"] = target_goal
        profile["goal_raw_semantic"] = (
            profile.get("goal_raw_semantic")
            or self._default_raw_semantic_for_goal(normalized_goal)
        )
        profile["goal_normalized_internal"] = normalized_goal
        profile["planning_strategy"] = (
            self._normalize_planning_strategy(profile.get("planning_strategy"))
            or self._default_planning_strategy_for_goal(normalized_goal)
        )
        profile["is_profile_completed"] = self.is_profile_completed(profile)
        return profile

    def is_profile_completed(self, profile: dict[str, Any]) -> bool:
        return all(
            self._has_profile_value(profile.get(field))
            for field in self._PROFILE_COMPLETION_REQUIRED_FIELDS
        )

    def _has_profile_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    def _normalize_goal(self, value: Any) -> Optional[str]:
        normalized = ascii_normalize(str(value or "")).replace("-", "_").replace(" ", "_")
        return GOAL_MAP.get(normalized, "maintain" if normalized else None)

    def _default_raw_semantic_for_goal(self, goal: Optional[str]) -> Optional[str]:
        return self._DEFAULT_RAW_SEMANTIC_BY_GOAL.get(goal or "")

    def _default_planning_strategy_for_goal(self, goal: Optional[str]) -> Optional[str]:
        return self._DEFAULT_PLANNING_STRATEGY_BY_GOAL.get(goal or "")

    def _normalize_planning_strategy(self, value: Any) -> Optional[str]:
        normalized = ascii_normalize(str(value or "")).replace(" ", "_")
        if not normalized:
            return None
        return normalized if normalized in STRATEGY_TO_GOAL_FAMILY else None

    def _resolve_planning_strategy(
        self,
        profile: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> Optional[str]:
        return (
            self._normalize_planning_strategy(profile.get("planning_strategy"))
            or self._normalize_planning_strategy(getattr(intent, "planning_strategy", None))
        )

    def _resolve_goal_family(
        self,
        profile: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> str:
        strategy = self._resolve_planning_strategy(profile, intent)
        if strategy:
            return STRATEGY_TO_GOAL_FAMILY.get(strategy, "maintain")
        return self._normalize_goal(profile.get("target_goal")) or "maintain"

    def _normalize_gender(self, value: Any) -> Optional[str]:
        normalized = ascii_normalize(str(value or ""))
        return GENDER_MAP.get(normalized, normalized or None)

    def _normalize_activity_level(self, value: Any) -> Optional[str]:
        normalized = ascii_normalize(str(value or "")).replace(" ", "_")
        return ACTIVITY_MAP.get(normalized, "moderate" if normalized else None)

    def _normalize_dietary_preference(self, value: Any) -> Optional[str]:
        normalized = ascii_normalize(str(value or "")).replace("-", "_").replace(" ", "_")
        return DIETARY_MAP.get(normalized, "omnivore" if normalized else None)

    def _normalize_text_list(self, value: Any) -> str:
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = str(value).replace(";", ",").replace("/", ",").split(",")
        cleaned = [str(item).strip() for item in raw_items if str(item).strip()]
        return ", ".join(dict.fromkeys(cleaned))

    def _normalize_allergies(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = str(value).replace(";", ",").replace("/", ",").split(",")

        tags: list[str] = []
        for item in raw_items:
            normalized = ascii_normalize(item).replace(" ", "_")
            if not normalized:
                continue
            tags.append(ALLERGY_MAP.get(normalized, normalized))
        return sorted(set(tags))

    def _compute_targets(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> WorkflowTargets:
        missing_fields = [
            field
            for field in ["age", "gender", "weight", "height", "activity_level"]
            if not profile.get(field)
        ]
        if missing_fields:
            raise ValueError(
                "Missing profile fields for nutrition planning: " + ", ".join(missing_fields)
            )
        goal_family = self._resolve_goal_family(profile)
        planning_strategy = self._resolve_planning_strategy(profile)

        tdee = NutritionService.calculate_tdee(
            age=int(profile["age"]),
            gender=str(profile["gender"]),
            weight=float(profile["weight"]),
            height=float(profile["height"]),
            activity_level=str(profile["activity_level"]),
        )
        macros = NutritionService.get_macro_targets(
            tdee,
            goal_family,
            dietary_preference=str(profile.get("dietary_preference", "omnivore")),
            weight=float(profile["weight"]),
            strategy=planning_strategy,
        )
        meal_targets = []
        for meal_name, ratio in MEAL_TEMPLATES.get(request.meal_count, MEAL_TEMPLATES[3]):
            meal_targets.append(
                {
                    "meal_name": meal_name,
                    "calories": round(macros["calories"] * ratio, 1),
                    "protein_g": round(macros["protein"] * ratio, 1),
                    "carbs_g": round(macros["carbs"] * ratio, 1),
                    "fat_g": round(macros["fat"] * ratio, 1),
                }
            )

        return {
            "tdee": round(tdee, 1),
            "daily_calories": round(macros["calories"], 1),
            "protein_g": round(macros["protein"], 1),
            "carbs_g": round(macros["carbs"], 1),
            "fat_g": round(macros["fat"], 1),
            "meal_targets": meal_targets,
            "calorie_tolerance_pct": request.calorie_tolerance_pct,
            "macro_tolerance_pct": request.macro_tolerance_pct,
        }
