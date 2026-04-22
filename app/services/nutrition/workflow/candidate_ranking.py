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


class WorkflowCandidateRankingMixin:
    def _goal_fit_score(
        self,
        candidate: dict[str, Any],
        goal: str,
        must_include: list[str],
        intent: Optional[NutritionIntent] = None,
        dietary_preference: Optional[str] = None,
    ) -> float:
        intent = intent if 'intent' in locals() else None  # Guard against NameError in all call paths/mixin scopes
        protein = safe_float(candidate.get("protein_g"), 0.0)
        carbs = safe_float(candidate.get("carbs_g"), 0.0)
        fat = safe_float(candidate.get("fat_g"), 0.0)
        energy = safe_float(candidate.get("energy_kcal"), 0.0)
        fiber = safe_float(candidate.get("fiber_g"), 0.0)
        quality = safe_float(candidate.get("quality_score"), 0.0)
        retrieval = safe_float(candidate.get("retrieval_score"), 0.0)
        planner_rank_weight = safe_float(candidate.get("planner_rank_weight"), 0.0)
        diet_tags = set(candidate.get("diet_tags") or [])
        role = self._candidate_role(candidate, goal)
        strategy = ascii_normalize(getattr(intent, 'planning_strategy', '')) if intent and getattr(intent, 'planning_strategy', None) else ""
        health_support_intent = self._is_health_support_retrieval_intent(intent)
        realism = self._candidate_realism_profile(candidate, goal)
        normalized_name = realism["normalized_name"]
        normalized_group = realism["normalized_group"]
        protein_preferred = any(keyword in normalized_name for keyword in PREFERRED_PROTEIN_KEYWORDS) or any(
            keyword in normalized_group for keyword in ["thit", "trung", "sua", "thuy san"]
        )
        carb_preferred = any(keyword in normalized_name for keyword in PREFERRED_CARB_KEYWORDS) or any(
            keyword in normalized_group for keyword in ["khoai", "ngu coc"]
        )

        matched_must_include = [item for item in must_include if self._candidate_matches_hint(candidate, item)]
        must_include_bonus = max(
            (
                0.6 if self._is_generic_support_hint(item) else 2.0
                for item in matched_must_include
            ),
            default=0.0,
        )
        produce_penalty = 0.0
        empty_density_penalty = 0.0
        practicality_penalty = 0.85 * len(realism["hard_block_reasons"]) + 0.22 * len(realism["discouraged_reasons"])
        practicality_bonus = 0.18 * len(realism["preferred_reasons"])

        if any(keyword in normalized_name for keyword in LOW_PRACTICALITY_KEYWORDS):
            practicality_penalty += 0.35
        if safe_float(candidate.get("sodium_mg"), 0.0) >= 900:
            practicality_penalty += 0.15
        if protein < 0 or carbs < 0 or fat < 0:
            practicality_penalty += 0.4
        if protein_preferred:
            practicality_bonus += 0.20
        if carb_preferred:
            practicality_bonus += 0.15
        if any(keyword in normalized_name for keyword in ["gao", "com", "ga", "trung", "dau hu", "tofu", "khoai", "yen mach"]):
            practicality_bonus += 0.15
        if role == "fat" and fat >= 25:
            practicality_penalty += 0.1
        if realism["hard_block"]:
            practicality_penalty += 1.5
        if health_support_intent and fat >= 18:
            empty_density_penalty += 0.22
        if health_support_intent and "trau" in normalized_name:
            practicality_penalty += 0.24
        if health_support_intent and normalized_name.endswith("hop"):
            practicality_penalty += 0.10

        if goal == "gain_muscle":
            score = (
                0.45 * min(protein / 30.0, 1.4)
                + 0.30 * min(carbs / 45.0, 1.3)
                + 0.20 * min(energy / 220.0, 1.3)
                + 0.08 * fiber
                + 0.25 * (1.0 if "high_protein" in diet_tags else 0.0)
                + 0.18 * (1.0 if "high_carb" in diet_tags else 0.0)
            )
            if role == "produce" and energy < 70 and protein < 8:
                produce_penalty = 0.55
            if energy < 50 and protein < 5 and carbs < 12:
                empty_density_penalty = 0.45
        elif goal == "lose_weight":
            protein_density = protein / max(energy, 1.0) * 100.0
            score = (
                0.45 * min(protein_density / 12.0, 1.5)
                + 0.20 * min(protein / 25.0, 1.2)
                + 0.22 * min(fiber / 6.0, 1.3)
                + 0.16 * (1.0 if "produce" in diet_tags else 0.0)
                + 0.10 * (1.0 if "low_fat" in diet_tags else 0.0)
                + 0.15 * (1.0 if 60 <= energy <= 220 else 0.0)
            )
            if protein >= 15 and fat <= 6:
                score += 0.18
            if self._is_healthy_fat_support(candidate, goal):
                score += 0.16
            if role == "balanced" and protein >= 12 and fat <= 12:
                score += 0.10
            if protein >= 15 and fat >= 8 and "low_fat" not in diet_tags:
                empty_density_penalty += 0.45
            if fat >= 12 and energy >= 180:
                empty_density_penalty += 0.18
            if fat > 18:
                empty_density_penalty += 0.20
        else:
            score = (
                0.35 * min(protein / 25.0, 1.3)
                + 0.25 * min(carbs / 35.0, 1.2)
                + 0.15 * min(fat / 12.0, 1.1)
                + 0.15 * (1.0 if "produce" in diet_tags else 0.0)
                + 0.10 * min(energy / 180.0, 1.1)
            )

        if (
            (strategy in {"maintenance_health_support", "deficit_balanced", "deficit_high_satiety"} or health_support_intent)
            and role == "produce"
            and protein < 8
            and carbs < 18
        ):
            produce_penalty += 0.25

        # ⭐ Boost ranking for high-protein vegetarian/vegan foods
        # Plant-based diets have fewer high-protein options, so we prioritize
        # foods that are both diet-compliant and protein-dense (tofu, tempeh,
        # legumes, seitan, etc.)
        veg_protein_bonus = 0.0
        if self._is_plant_based_diet(dietary_preference):
            is_veg_food = any(tag in diet_tags for tag in ("vegetarian", "vegan"))
            if is_veg_food and protein >= 12:
                # Strong bonus for high-protein plant foods
                veg_protein_bonus = 0.35 * min(protein / 20.0, 1.5)
            elif is_veg_food and protein >= 8:
                # Moderate bonus for decent-protein plant foods
                veg_protein_bonus = 0.18 * min(protein / 15.0, 1.2)

        # Fix for NameError + edge cases: define here in scoring scope (soft diversity, dynamic penalty 0.25-0.35 capped). Safe intent default.
        realism = self._candidate_realism_profile(candidate, goal)
        role = self._candidate_role(candidate, goal)
        discouraged_penalty = 0.0
        planning_strategy = getattr(intent, 'planning_strategy', '') if 'intent' in locals() else ''
        if realism.get("discouraged_reasons"):
            severity = 0.35 if goal in ("lose_weight", "fat_loss", "eat_healthier") or "budget" in planning_strategy.lower() else 0.25
            discouraged_penalty = severity * min(len(realism.get("discouraged_reasons", [])), 3)
        diversity_boost = 0.12 if role in ("protein", "produce", "carb") else 0.0

        return (
            0.55 * score
            + 0.20 * retrieval
            + 0.15 * quality
            + 0.22 * planner_rank_weight
            + must_include_bonus
            + practicality_bonus
            + veg_protein_bonus
            + self._intent_alignment_score(candidate, goal, intent)
            + diversity_boost
            - produce_penalty
            - empty_density_penalty
            - practicality_penalty
            - discouraged_penalty
        )

    def _intent_alignment_score(
        self,
        candidate: dict[str, Any],
        goal: str,
        intent: Optional[NutritionIntent],
    ) -> float:
        if intent is None:
            return 0.0

        score = 0.0
        normalized_name = ascii_normalize(candidate.get("name"))
        normalized_group = ascii_normalize(candidate.get("group_name"))
        protein = safe_float(candidate.get("protein_g"), 0.0)
        carbs = safe_float(candidate.get("carbs_g"), 0.0)
        fat = safe_float(candidate.get("fat_g"), 0.0)
        fiber = safe_float(candidate.get("fiber_g"), 0.0)
        energy = safe_float(candidate.get("energy_kcal"), 0.0)
        meal_role_tags = set(candidate.get("meal_role_tags") or [])
        realism = self._candidate_realism_profile(candidate, goal)
        role = self._candidate_role(candidate, goal)
        preferred_hints = [
            *(intent.soft_preferences.preferred_foods or []),
            *(intent.soft_preferences.must_include or []),
        ]
        disliked_hints = [
            *(intent.soft_preferences.disliked_foods or []),
            *(intent.hard_constraints.must_avoid or []),
        ]

        preferred_bonus = max(
            (
                0.12 if self._is_generic_support_hint(item) else 0.45
                for item in preferred_hints
                if self._candidate_matches_hint(candidate, item)
            ),
            default=0.0,
        )
        score += preferred_bonus
        if any(self._candidate_matches_hint(candidate, item) for item in disliked_hints):
            score -= 0.9

        priorities = set(intent.priorities or [])
        if "protein" in priorities and protein >= 18:
            score += 0.20
        if "satiety" in priorities and (protein >= 12 or fiber >= 4):
            score += 0.18
        if "recovery" in priorities and protein >= 15 and carbs >= 20:
            score += 0.22
        if "simplicity" in priorities and any(keyword in normalized_name for keyword in COMMON_MEAL_FOOD_KEYWORDS):
            score += 0.12
        if "budget" in priorities and any(keyword in normalized_name for keyword in AFFORDABLE_FOOD_KEYWORDS):
            score += 0.14
        if "lightness" in priorities and 60 <= energy <= 220 and fat <= 12:
            score += 0.14
        if "micronutrients" in priorities and ("produce" in (candidate.get("diet_tags") or []) or "rau" in normalized_group):
            score += 0.12

        if intent.soft_preferences.cooking_complexity == "easy":
            if any(keyword in normalized_name for keyword in COMMON_MEAL_FOOD_KEYWORDS):
                score += 0.10
            if realism["discouraged_reasons"]:
                score -= 0.15
        if intent.soft_preferences.budget_level == "low":
            if any(keyword in normalized_name for keyword in AFFORDABLE_FOOD_KEYWORDS):
                score += 0.10
            if protein >= 20 and energy >= 280 and "trung ca" in normalized_name:
                score -= 0.15
        if intent.soft_preferences.meal_style == "high_protein" and protein >= 18:
            score += 0.15
        if intent.soft_preferences.meal_style == "light" and energy <= 220 and fat <= 12:
            score += 0.12
        if intent.soft_preferences.meal_style == "traditional" and any(
            keyword in normalized_name for keyword in ["com", "gao", "ga", "ca", "rau", "thit", "dau hu"]
        ):
            score += 0.08

        if intent.meal_preferences.satiety_preference == "high" and (protein >= 12 or fiber >= 4):
            score += 0.12
        if intent.meal_preferences.post_workout_meal and protein >= 18 and carbs >= 20:
            score += 0.14
        if (
            intent.meal_preferences.post_workout_meal
            and role == "carb"
            and fat <= 5
            and any(keyword in normalized_name for keyword in ["gao", "com", "pho", "nui", "yen mach", "khoai"])
        ):
            score += 0.14
        if (
            intent.meal_preferences.post_workout_meal
            and role == "protein"
            and ("thuy san" in normalized_group or normalized_name.startswith("ca "))
            and protein >= 10
            and fat <= 10
        ):
            score += 0.12
        if intent.meal_preferences.pre_workout_meal and 15 <= carbs <= 45 and fat <= 15:
            score += 0.10
        if intent.meal_preferences.late_dinner and fat >= 18:
            score -= 0.12

        if self._is_health_support_retrieval_intent(intent):
            if 60 <= energy <= 240 and fat <= 12:
                score += 0.08
            if "thuy san" in normalized_group and protein >= 10 and fat <= 10:
                score += 0.18
            if "ga" in normalized_name and fat <= 10:
                score += 0.12
            if any(keyword in normalized_name for keyword in ["pho", "chao", "sup"]):
                score += 0.18
            if any(keyword in normalized_name for keyword in ["gao", "com", "rice"]) and fat <= 6:
                score += 0.08
            if "produce_support" in meal_role_tags and energy <= 120:
                score += 0.06
            if "trau" in normalized_name or "trau" in normalized_group:
                score -= 0.22
            if normalized_name.endswith("hop"):
                score -= 0.18
            if fat >= 18:
                score -= 0.24
            if role == "produce" and protein < 6 and carbs < 15:
                score -= 0.08

        return score

    def _must_include_preference_score(self, candidate: dict[str, Any], hint: str) -> float:
        normalized_hint = ascii_normalize(hint)
        normalized_name = ascii_normalize(candidate.get("name"))
        normalized_group = ascii_normalize(candidate.get("group_name"))
        meal_role_tags = set(candidate.get("meal_role_tags") or [])
        protein = safe_float(candidate.get("protein_g"), 0.0)
        carbs = safe_float(candidate.get("carbs_g"), 0.0)
        bonus = 0.0

        if self._is_generic_support_hint(normalized_hint):
            if "protein_anchor" in meal_role_tags:
                bonus += 1.0
            if "carb_anchor" in meal_role_tags:
                bonus += 0.8
            if "produce_support" in meal_role_tags:
                bonus += 0.3
            if protein < 6 and carbs < 15:
                bonus -= 0.8

        if normalized_hint == "trung":
            if "trung" in normalized_group or "egg" in normalized_name:
                bonus += 2.0
            if normalized_name.startswith("con ") or "shellfish" in (candidate.get("allergen_tags") or []):
                bonus -= 2.0
        elif normalized_hint in {"gao", "com"}:
            if "ngu coc" in normalized_group or any(keyword in normalized_name for keyword in ["gao", "com", "rice"]):
                bonus += 0.8
            if "dau" in normalized_group or "dau" in normalized_name:
                bonus -= 0.4
        elif normalized_hint == "rau xanh":
            if "rau" in normalized_group or normalized_name.startswith("rau "):
                bonus += 0.6
            if any(keyword in normalized_name for keyword in ["xoi ", "qua ", ", kho", " kho "]):
                bonus -= 1.5
        elif normalized_hint == "uc ga":
            if "ga" in normalized_name and "thit" in normalized_name:
                bonus += 2.0
            if any(keyword in normalized_name for keyword in ["long ", "me ", "gan "]):
                bonus -= 1.0
        elif normalized_hint in {"dau hu", "dau phu"}:
            if any(keyword in normalized_name for keyword in ["dau phu", "dau hu", "tofu"]):
                bonus += 2.4
            if any(keyword in normalized_name for keyword in [", kho", " kho "]):
                bonus -= 1.5
        elif normalized_hint in {"dau xanh", "dau den"}:
            if any(keyword in normalized_name for keyword in ["dau phu", "dau hu", "tofu", "hat bi do"]):
                bonus += 1.6
            if any(keyword in normalized_name for keyword in ["xoi do", "hat sen"]):
                bonus += 0.8
            if any(keyword in normalized_name for keyword in [", kho", " kho "]):
                bonus -= 1.6
        elif normalized_hint in {"hat bi do", "hat bi o"}:
            if "hat bi" in normalized_name:
                bonus += 2.2
        elif normalized_hint in {"yen mach", "gao lut"}:
            if any(keyword in normalized_name for keyword in ["hat sen", "khoai", "ngo", "bun", "nui"]):
                bonus += 1.0
            if "gao" in normalized_name and "song" in normalized_name:
                bonus -= 2.0

        return bonus
