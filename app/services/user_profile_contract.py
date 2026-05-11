from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


PUBLIC_CURRENT_USER_FIELDS = (
    "id",
    "username",
    "email",
    "full_name",
    "phone",
    "referral_code",
    "avatar_url",
    "is_active",
    "created_at",
    "age",
    "gender",
    "weight",
    "height",
    "activity_level",
    "workouts_per_week",
    "workout_minutes",
    "training_types",
    "dietary_preference",
    "allergies",
    "disliked_foods",
    "favorite_meals",
    "avoid_meals",
    "medical_conditions",
    "target_goal",
)

AUTH_PROFILE_CONTRACT_FIELDS = (
    "age",
    "gender",
    "weight",
    "height",
    "activity_level",
    "target_goal",
    "goal_raw_semantic",
    "goal_normalized_internal",
    "planning_strategy",
    "is_profile_completed",
)


def build_current_user_contract(
    current_user: Mapping[str, Any],
    *,
    permissions: Iterable[str],
    nutrition_profile: Mapping[str, Any],
) -> dict[str, Any]:
    user_payload = {
        field: current_user.get(field)
        for field in PUBLIC_CURRENT_USER_FIELDS
        if field in current_user
    }

    for field in AUTH_PROFILE_CONTRACT_FIELDS:
        user_payload[field] = nutrition_profile.get(field)

    user_payload["permissions"] = sorted({str(permission) for permission in permissions})
    return user_payload
