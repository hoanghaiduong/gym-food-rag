from __future__ import annotations

import re
from typing import Any, Optional

from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize, safe_float

from .constants import (
    AFFORDABLE_FOOD_KEYWORDS,
    COMMON_MEAL_FOOD_KEYWORDS,
    LOW_PRACTICALITY_KEYWORDS,
    PREFERRED_CARB_KEYWORDS,
    PREFERRED_PROTEIN_KEYWORDS,
    REALISM_DISCOURAGED_NAME_KEYWORDS,
    REALISM_HARD_BLOCK_GROUP_KEYWORDS,
    REALISM_HARD_BLOCK_NAME_KEYWORDS,
)


class WorkflowCandidateRolesMixin:
    def _candidate_role(self, candidate: dict[str, Any], goal: str) -> str:
        protein = safe_float(candidate.get("protein_g"), 0.0)
        carbs = safe_float(candidate.get("carbs_g"), 0.0)
        fat = safe_float(candidate.get("fat_g"), 0.0)
        energy = safe_float(candidate.get("energy_kcal"), 0.0)
        diet_tags = set(candidate.get("diet_tags") or [])
        meal_role_tags = set(candidate.get("meal_role_tags") or [])
        normalized_name = ascii_normalize(candidate.get("name"))
        normalized_group = ascii_normalize(candidate.get("group_name"))
        produce_like = self._is_produce_like_candidate(candidate)

        is_protein_preferred = any(keyword in normalized_name for keyword in PREFERRED_PROTEIN_KEYWORDS) or any(
            keyword in normalized_group for keyword in ["thit", "trung", "sua", "thuy san", "hat", "dau"]
        )
        is_carb_preferred = any(keyword in normalized_name for keyword in PREFERRED_CARB_KEYWORDS) or any(
            keyword in normalized_group for keyword in ["khoai", "ngu coc", "bot", "banh mi"]
        )
        carb_dominant_dual_anchor = (
            "protein_anchor" in meal_role_tags
            and "carb_anchor" in meal_role_tags
            and (
                is_carb_preferred
                or any(
                    keyword in normalized_name
                    for keyword in ["nui", "bun", "pho", "gao", "com", "ngo", "khoai", "xoi", "mien", "mi "]
                )
            )
            and carbs >= max(protein * 2.5, 25.0)
            and fat <= max(protein, 10.0)
        )
        tofu_like = any(keyword in normalized_name for keyword in ["dau phu", "dau hu", "tofu"])
        seed_protein_like = any(
            keyword in normalized_name
            for keyword in ["hat bi do", "hat de cuoi", "hat huong duong"]
        ) or (
            normalized_name.startswith("hat ")
            and protein >= 18
            and fat <= 55
            and ("protein_anchor" in meal_role_tags or "high_protein" in diet_tags)
        )

        if tofu_like and protein >= 8:
            return "protein"
        if seed_protein_like:
            return "protein"
        if fat >= 20 and energy >= 250:
            return "fat"
        if fat >= 20 and energy >= 250 and not is_protein_preferred:
            return "fat"
        if produce_like and not is_protein_preferred and not is_carb_preferred:
            if carbs >= 25:
                return "carb"
            return "produce"
        if (
            "protein_anchor" in meal_role_tags
            and not carb_dominant_dual_anchor
            and not (produce_like and not is_protein_preferred)
        ):
            return "protein"
        if "carb_anchor" in meal_role_tags and not (produce_like and not is_carb_preferred and carbs < 30):
            return "carb"
        if "produce_support" in meal_role_tags:
            if fat >= 18 and energy >= 220:
                return "fat"
            if protein >= 12 and ("protein_anchor" in meal_role_tags or is_protein_preferred):
                return "protein"
            return "produce"

        is_produce_group = (
            "rau" in normalized_group
            or "trai cay" in normalized_group
            or ("produce" in diet_tags and fat < 12 and protein < 18)
        )

        if goal == "lose_weight" and protein >= 15 and fat >= 8 and "low_fat" not in diet_tags:
            return "balanced"
        if normalized_name.startswith("hat ") and carbs >= 20:
            return "carb"
        if any(normalized_name.startswith(prefix) for prefix in ["xoi ", "che ", "banh "]) and carbs >= 20:
            return "carb"
        if is_produce_group or ("produce" in diet_tags and energy <= 160 and protein < 18):
            return "produce"
        if is_protein_preferred and protein >= 10:
            return "protein"
        if is_carb_preferred and carbs >= 18:
            return "carb"
        if protein >= 24 or ("high_protein" in diet_tags and fat < 20):
            return "protein"
        if carbs >= 25 or "high_carb" in diet_tags:
            return "carb"
        if goal == "lose_weight" and "produce" in diet_tags:
            return "produce"
        return "balanced"

    def _candidate_is_main_meal_protein_anchor(
        self,
        candidate: dict[str, Any],
        goal: str,
        dietary_preference: Optional[str] = None,
    ) -> bool:
        if self._candidate_role(candidate, goal) == "protein":
            return True
        if not self._is_plant_based_diet(dietary_preference):
            return False

        meal_role_tags = {ascii_normalize(tag) for tag in (candidate.get("meal_role_tags") or [])}
        if "protein_anchor" not in meal_role_tags:
            return False
        protein = safe_float(candidate.get("protein_g"), 0.0)
        carbs = safe_float(candidate.get("carbs_g"), 0.0)
        fat = safe_float(candidate.get("fat_g"), 0.0)
        if protein < 4:
            return False
        # Avoid counting pasta/staples as the only protein anchor just because
        # their source data carries a broad protein tag.
        if carbs > max(protein * 2.5, 20.0) and fat < protein:
            return False
        return True

    def _is_healthy_fat_support(self, candidate: dict[str, Any], goal: str) -> bool:
        realism = self._candidate_realism_profile(candidate, goal)
        if realism["hard_block"]:
            return False
        normalized_name = realism["normalized_name"]
        normalized_group = realism["normalized_group"]
        fat = safe_float(candidate.get("fat_g"), 0.0)
        protein = safe_float(candidate.get("protein_g"), 0.0)
        energy = safe_float(candidate.get("energy_kcal"), 0.0)
        diet_tags = set(candidate.get("diet_tags") or [])
        avocado_like = any(keyword in normalized_name for keyword in ["qua bo", "bo vo", "avocado"])
        portion_safe_nut = any(
            keyword in normalized_name
            for keyword in [
                "hat macca",
                "hat oc cho",
                "hat de cuoi",
                "hanh nhan",
                "macadamia",
                "walnut",
                "pistachio",
                "almond",
            ]
        ) and any(keyword in normalized_name for keyword in ["rang", "roasted"])

        if fat < 4 or energy < 40:
            return False
        if energy > 320 and not portion_safe_nut:
            return False
        if fat > 24 and not portion_safe_nut:
            return False
        if any(keyword in normalized_name for keyword in ["banh ", "che ", "kem", "nuoc ngot", "tra sua"]):
            return False
        if avocado_like:
            return True
        if (
            normalized_name.startswith(("ga ", "bo ", "heo ", "lon ", "thit "))
            or any(keyword in normalized_name for keyword in ["thit ", " ga", "bo ", "heo", "lon "])
        ) and not any(
            keyword in normalized_name for keyword in ["trung", "ca ", "ca hoi", "ca trich", "fish"]
        ):
            return False
        if "thit" in normalized_group and not any(keyword in normalized_name for keyword in ["trung", "ca "]):
            return False
        if portion_safe_nut and protein <= max(10.0, fat * 0.35):
            return True
        if any(keyword in normalized_name for keyword in ["trung", "egg", "salmon", "ca hoi", "avocado", "bo qua", "qua bo", "hat ", "hanh nhan", "hat dieu", "oc cho", "yogurt", "sua chua"]):
            return True
        if any(keyword in normalized_group for keyword in ["sua", "thuy san", "hat"]):
            return True
        if protein >= 6 and fat >= 6:
            return True
        if goal in {"lose_weight", "maintain"} and "low_fat" not in diet_tags and 6 <= fat <= 18:
            return True
        return False

    def _healthy_fat_candidates(self, candidates: list[dict[str, Any]], goal: str) -> list[dict[str, Any]]:
        return [item for item in candidates if self._is_healthy_fat_support(item, goal)]
