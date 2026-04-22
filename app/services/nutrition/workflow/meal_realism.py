from __future__ import annotations

from typing import Any, Optional

from app.services.nutrition_knowledge_service import ascii_normalize, safe_float

from .constants import MAIN_MEAL_NAMES, PORTION_CAP_BY_NAME_KEYWORDS
from .strings_vi import (
    MEAL_REALISM_ADD_PROTEIN_REASON,
    MEAL_REALISM_ADD_STAPLE_REASON,
)


class WorkflowMealRealismMixin:
    def _is_main_meal_name(self, meal_name: str) -> bool:
        return ascii_normalize(meal_name) in MAIN_MEAL_NAMES

    def _is_produce_like_candidate(self, candidate: dict[str, Any]) -> bool:
        normalized_name = ascii_normalize(candidate.get("name") or candidate.get("food_name"))
        normalized_group = ascii_normalize(candidate.get("group_name"))
        diet_tags = {ascii_normalize(tag) for tag in (candidate.get("diet_tags") or []) if ascii_normalize(tag)}
        meal_role_tags = {
            ascii_normalize(tag) for tag in (candidate.get("meal_role_tags") or []) if ascii_normalize(tag)
        }
        return bool(
            "produce_support" in meal_role_tags
            or "rau" in normalized_group
            or "trai cay" in normalized_group
            or "qua chin" in normalized_group
            or normalized_name.startswith(("rau ", "qua ", "trai "))
            or ("produce" in diet_tags and not any(keyword in normalized_group for keyword in ["hat", "sua", "ngu coc"]))
        )

    def _portion_cap_for_candidate(
        self,
        candidate: dict[str, Any],
        goal: str,
        meal_name: Optional[str] = None,
    ) -> int:
        normalized_name = ascii_normalize(candidate.get("name") or candidate.get("food_name"))
        normalized_group = ascii_normalize(candidate.get("group_name"))
        preparation_style = ascii_normalize(candidate.get("preparation_style"))
        role = self._candidate_role(candidate, goal)
        is_main_meal = self._is_main_meal_name(meal_name or "")

        for keyword, cap in PORTION_CAP_BY_NAME_KEYWORDS.items():
            if keyword in normalized_name:
                return cap

        if role == "protein":
            return 180 if is_main_meal else 160
        if role == "carb":
            return 220
        if role == "balanced":
            return 140
        if role == "fat":
            return 45 if is_main_meal else 35
        if role == "produce":
            if "trai cay" in normalized_group or "qua chin" in normalized_group:
                return 100
            if "rau" in normalized_group or preparation_style in {"boiled", "raw"} or "luoc" in normalized_name:
                return 130 if is_main_meal else 150
            return 130
        return 180

    def _seed_grams_for_candidate(
        self,
        candidate: dict[str, Any],
        goal: str,
        meal_name: Optional[str] = None,
    ) -> int:
        role = self._candidate_role(candidate, goal)
        normalized_meal_name = ascii_normalize(meal_name or "")
        if role == "protein":
            target = 100 if normalized_meal_name == "breakfast" else 120
        elif role == "carb":
            target = 90 if normalized_meal_name == "breakfast" else 120
        elif role == "balanced":
            target = 80
        elif role == "fat":
            target = 60
        else:
            target = 80
        return max(30, min(target, self._portion_cap_for_candidate(candidate, goal, meal_name)))

    def _build_blueprint_item_from_candidate(
        self,
        candidate: dict[str, Any],
        goal: str,
        meal_name: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "entity_id": candidate.get("entity_id"),
            "food_name": candidate.get("name"),
            "grams": self._seed_grams_for_candidate(candidate, goal, meal_name),
            "reason": reason,
        }

    def _apply_portion_cap_to_meal_item(
        self,
        item: dict[str, Any],
        candidate_lookup: dict[str, dict[str, Any]],
        goal: str,
        meal_name: str,
    ) -> dict[str, Any]:
        adjusted = dict(item)
        candidate = candidate_lookup.get(adjusted.get("entity_id"))
        current_grams = max(int(round(safe_float(adjusted.get("grams"), 0.0))), 0)
        if candidate is None:
            adjusted["grams"] = max(30, min(current_grams or 120, 400))
            return adjusted

        portion_cap = self._portion_cap_for_candidate(candidate, goal, meal_name)
        seed_grams = self._seed_grams_for_candidate(candidate, goal, meal_name)
        adjusted["grams"] = max(30, min(current_grams or seed_grams, portion_cap))
        return adjusted

    def _select_anchor_candidate(
        self,
        candidate_pool: list[dict[str, Any]],
        goal: str,
        desired_roles: list[str],
        used_entity_ids: set[str],
    ) -> Optional[dict[str, Any]]:
        for role in desired_roles:
            for candidate in candidate_pool:
                entity_id = candidate.get("entity_id")
                if entity_id and entity_id in used_entity_ids:
                    continue
                realism = self._candidate_realism_profile(candidate, goal)
                if realism["hard_block"]:
                    continue
                if any(
                    reason in {"very_high_fat", "specialty_or_low_practicality", "meal_ready_policy_discouraged"}
                    for reason in realism["discouraged_reasons"]
                ):
                    continue
                if self._candidate_role(candidate, goal) == role:
                    return candidate
        return None

    def _enforce_meal_realism_blueprint(
        self,
        meal_name: str,
        items: list[dict[str, Any]],
        candidate_pool: list[dict[str, Any]],
        goal: str,
        *,
        balanced_meal_required: bool = False,
    ) -> list[dict[str, Any]]:
        candidate_lookup = {
            candidate.get("entity_id"): candidate
            for candidate in candidate_pool
            if candidate.get("entity_id")
        }
        used_entity_ids: set[str] = set()
        normalized_items: list[dict[str, Any]] = []
        for raw_item in items:
            adjusted = self._apply_portion_cap_to_meal_item(raw_item, candidate_lookup, goal, meal_name)
            entity_id = adjusted.get("entity_id")
            if entity_id and entity_id in used_entity_ids:
                continue
            if entity_id:
                used_entity_ids.add(entity_id)
            normalized_items.append(adjusted)

        if not self._is_main_meal_name(meal_name):
            return normalized_items[:5]

        def current_roles() -> list[str]:
            roles: list[str] = []
            for item in normalized_items:
                candidate = candidate_lookup.get(item.get("entity_id"))
                if candidate is None:
                    continue
                roles.append(self._candidate_role(candidate, goal))
            return roles

        roles = current_roles()
        if not any(role == "protein" for role in roles):
            protein_candidate = self._select_anchor_candidate(candidate_pool, goal, ["protein"], used_entity_ids)
            if protein_candidate is not None:
                normalized_items.insert(
                    0,
                    self._build_blueprint_item_from_candidate(
                        protein_candidate,
                        goal,
                        meal_name,
                        MEAL_REALISM_ADD_PROTEIN_REASON,
                    ),
                )
                if protein_candidate.get("entity_id"):
                    used_entity_ids.add(protein_candidate["entity_id"])
                roles = current_roles()

        single_support_meal = len(normalized_items) == 1 and all(role in {"produce", "balanced", "fat"} for role in roles)
        needs_staple = balanced_meal_required and not any(role == "carb" for role in roles)
        if single_support_meal or needs_staple:
            staple_candidate = self._select_anchor_candidate(candidate_pool, goal, ["carb", "balanced"], used_entity_ids)
            if staple_candidate is not None:
                normalized_items.append(
                    self._build_blueprint_item_from_candidate(
                        staple_candidate,
                        goal,
                        meal_name,
                        MEAL_REALISM_ADD_STAPLE_REASON,
                    )
                )
                if staple_candidate.get("entity_id"):
                    used_entity_ids.add(staple_candidate["entity_id"])
                roles = current_roles()

        role_priority = {"protein": 0, "carb": 1, "balanced": 2, "produce": 3, "fat": 4}
        normalized_items.sort(
            key=lambda item: (
                role_priority.get(
                    self._candidate_role(candidate_lookup[item["entity_id"]], goal)
                    if item.get("entity_id") in candidate_lookup
                    else "balanced",
                    9,
                ),
                -safe_float(item.get("grams"), 0.0),
            )
        )
        return normalized_items[:5]
