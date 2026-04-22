from __future__ import annotations

from typing import Any

from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize

from .taxonomy import (
    BUDGET_LEVEL_ALIASES,
    CHAT_CLARIFY_GOALS,
    COOKING_COMPLEXITY_ALIASES,
    MEAL_STYLE_ALIASES,
    SATIETY_ALIASES,
)


class IntentMergingMixin:
    def _normalize_payload(self, payload: dict[str, Any], source: str) -> NutritionIntent:
        hard_constraints = payload.get("hard_constraints") or {}
        soft_preferences = payload.get("soft_preferences") or {}
        meal_preferences = payload.get("meal_preferences") or {}
        raw_goal = self._normalize_raw_semantic_goal(payload.get("goal_raw_semantic") or payload.get("goal_raw") or payload.get("goal"))
        normalized_goal = self._normalize_internal_goal(payload.get("goal_normalized_internal") or payload.get("goal"))
        if not normalized_goal and raw_goal:
            normalized_goal = self._goal_family_from_raw(raw_goal)
        strategy = self._normalize_planning_strategy(payload.get("planning_strategy"))
        if not strategy:
            strategy = self._infer_planning_strategy(
                raw_goal=raw_goal,
                normalized_goal=normalized_goal,
                priorities=self._normalize_priorities(payload.get("priorities")),
                meal_preferences=meal_preferences,
                soft_preferences=soft_preferences,
            )
        if not normalized_goal and strategy:
            normalized_goal = self._goal_family_from_strategy(strategy)
        if not raw_goal and normalized_goal:
            raw_goal = self._default_raw_semantic_for_internal(normalized_goal)

        normalized_payload = {
            "goal_raw_semantic": raw_goal,
            "goal_normalized_internal": normalized_goal,
            "planning_strategy": strategy,
            "goal": normalized_goal,
            "priorities": self._normalize_priorities(payload.get("priorities")),
            "hard_constraints": {
                "dietary_preference": self._normalize_dietary_preference(hard_constraints.get("dietary_preference")),
                "allergies": self._normalize_allergies(hard_constraints.get("allergies")),
                "must_avoid": self._clean_food_list(hard_constraints.get("must_avoid")),
            },
            "soft_preferences": {
                "must_include": self._clean_food_list(soft_preferences.get("must_include")),
                "preferred_foods": self._clean_food_list(soft_preferences.get("preferred_foods")),
                "disliked_foods": self._clean_food_list(soft_preferences.get("disliked_foods")),
                "cooking_complexity": self._normalize_choice(soft_preferences.get("cooking_complexity"), COOKING_COMPLEXITY_ALIASES),
                "budget_level": self._normalize_choice(soft_preferences.get("budget_level"), BUDGET_LEVEL_ALIASES),
                "meal_style": self._normalize_choice(soft_preferences.get("meal_style"), MEAL_STYLE_ALIASES),
            },
            "meal_preferences": {
                "meal_count": self._normalize_meal_count(meal_preferences.get("meal_count")),
                "pre_workout_meal": bool(meal_preferences.get("pre_workout_meal")),
                "post_workout_meal": bool(meal_preferences.get("post_workout_meal")),
                "late_dinner": bool(meal_preferences.get("late_dinner")),
                "satiety_preference": self._normalize_choice(meal_preferences.get("satiety_preference"), SATIETY_ALIASES),
            },
            "notes": self._clean_food_list(payload.get("notes"), max_items=6),
            "confidence": self._normalize_confidence(payload.get("confidence")),
            "source": source,
        }
        return NutritionIntent.model_validate(normalized_payload)

    def _merge_intents(self, base: NutritionIntent, overlay: NutritionIntent) -> NutritionIntent:
        merged = base.model_copy(deep=True)
        if overlay.goal_raw_semantic:
            merged.goal_raw_semantic = overlay.goal_raw_semantic
        if overlay.goal_normalized_internal:
            merged.goal_normalized_internal = overlay.goal_normalized_internal
            merged.goal = overlay.goal_normalized_internal
        elif overlay.goal:
            merged.goal = overlay.goal
            merged.goal_normalized_internal = overlay.goal
        if overlay.planning_strategy:
            merged.planning_strategy = overlay.planning_strategy
        merged.priorities = self._merge_list(merged.priorities, overlay.priorities)
        merged.notes = self._merge_list(merged.notes, overlay.notes, max_items=8)
        merged.confidence = max(float(merged.confidence or 0.0), float(overlay.confidence or 0.0))
        merged.source = overlay.source or merged.source

        if not merged.goal_normalized_internal and merged.goal:
            merged.goal_normalized_internal = merged.goal
        if not merged.goal and merged.goal_normalized_internal:
            merged.goal = merged.goal_normalized_internal
        if not merged.goal_raw_semantic and merged.goal_normalized_internal:
            merged.goal_raw_semantic = self._default_raw_semantic_for_internal(merged.goal_normalized_internal)
        if not merged.planning_strategy:
            merged.planning_strategy = self._default_strategy_for_goal(merged.goal_normalized_internal)

        if overlay.hard_constraints.dietary_preference:
            merged.hard_constraints.dietary_preference = overlay.hard_constraints.dietary_preference
        merged.hard_constraints.allergies = self._merge_list(merged.hard_constraints.allergies, overlay.hard_constraints.allergies)
        merged.hard_constraints.must_avoid = self._merge_list(merged.hard_constraints.must_avoid, overlay.hard_constraints.must_avoid)
        merged.soft_preferences.must_include = self._merge_list(merged.soft_preferences.must_include, overlay.soft_preferences.must_include)
        merged.soft_preferences.preferred_foods = self._merge_list(merged.soft_preferences.preferred_foods, overlay.soft_preferences.preferred_foods)
        merged.soft_preferences.disliked_foods = self._merge_list(merged.soft_preferences.disliked_foods, overlay.soft_preferences.disliked_foods)
        if overlay.soft_preferences.cooking_complexity:
            merged.soft_preferences.cooking_complexity = overlay.soft_preferences.cooking_complexity
        if overlay.soft_preferences.budget_level:
            merged.soft_preferences.budget_level = overlay.soft_preferences.budget_level
        if overlay.soft_preferences.meal_style:
            merged.soft_preferences.meal_style = overlay.soft_preferences.meal_style

        if overlay.meal_preferences.meal_count:
            merged.meal_preferences.meal_count = overlay.meal_preferences.meal_count
        merged.meal_preferences.pre_workout_meal = merged.meal_preferences.pre_workout_meal or overlay.meal_preferences.pre_workout_meal
        merged.meal_preferences.post_workout_meal = merged.meal_preferences.post_workout_meal or overlay.meal_preferences.post_workout_meal
        merged.meal_preferences.late_dinner = merged.meal_preferences.late_dinner or overlay.meal_preferences.late_dinner
        if overlay.meal_preferences.satiety_preference:
            merged.meal_preferences.satiety_preference = overlay.meal_preferences.satiety_preference
        return merged

    def _prefer_more_specific_goal(
        self,
        *,
        default_intent: NutritionIntent,
        heuristic_intent: NutritionIntent,
        llm_intent: NutritionIntent,
        final_intent: NutritionIntent,
    ) -> NutritionIntent:
        default_signature = (default_intent.goal_raw_semantic, default_intent.goal_normalized_internal or default_intent.goal, default_intent.planning_strategy)
        heuristic_signature = (heuristic_intent.goal_raw_semantic, heuristic_intent.goal_normalized_internal or heuristic_intent.goal, heuristic_intent.planning_strategy)
        llm_signature = (llm_intent.goal_raw_semantic, llm_intent.goal_normalized_internal or llm_intent.goal, llm_intent.planning_strategy)

        heuristic_specific = heuristic_signature != default_signature and any(heuristic_signature)
        llm_specific = llm_signature != default_signature and any(llm_signature)
        if heuristic_specific and not llm_specific:
            final_intent.goal_raw_semantic = heuristic_intent.goal_raw_semantic
            final_intent.goal_normalized_internal = heuristic_intent.goal_normalized_internal or heuristic_intent.goal
            final_intent.goal = final_intent.goal_normalized_internal
            final_intent.planning_strategy = heuristic_intent.planning_strategy
        return final_intent

    def _prefer_explicit_heuristic_constraints(
        self,
        *,
        heuristic_intent: NutritionIntent,
        final_intent: NutritionIntent,
    ) -> NutritionIntent:
        if heuristic_intent.hard_constraints.dietary_preference:
            final_intent.hard_constraints.dietary_preference = heuristic_intent.hard_constraints.dietary_preference
        if heuristic_intent.hard_constraints.allergies:
            final_intent.hard_constraints.allergies = heuristic_intent.hard_constraints.allergies
        if heuristic_intent.hard_constraints.must_avoid:
            final_intent.hard_constraints.must_avoid = self._merge_list(
                final_intent.hard_constraints.must_avoid,
                heuristic_intent.hard_constraints.must_avoid,
            )
        return final_intent

    def _should_short_circuit_llm(
        self,
        *,
        instruction: str,
        default_intent: NutritionIntent,
        heuristic_intent: NutritionIntent,
    ) -> bool:
        normalized_instruction = ascii_normalize(instruction)
        if not normalized_instruction:
            return True

        default_signature = (
            default_intent.goal_raw_semantic,
            default_intent.goal_normalized_internal or default_intent.goal,
            default_intent.planning_strategy,
            tuple(default_intent.hard_constraints.allergies or []),
            default_intent.hard_constraints.dietary_preference,
            tuple(default_intent.hard_constraints.must_avoid or []),
            tuple(default_intent.soft_preferences.must_include or []),
            default_intent.meal_preferences.meal_count,
            default_intent.meal_preferences.satiety_preference,
            default_intent.meal_preferences.post_workout_meal,
            default_intent.meal_preferences.pre_workout_meal,
        )
        heuristic_signature = (
            heuristic_intent.goal_raw_semantic,
            heuristic_intent.goal_normalized_internal or heuristic_intent.goal,
            heuristic_intent.planning_strategy,
            tuple(heuristic_intent.hard_constraints.allergies or []),
            heuristic_intent.hard_constraints.dietary_preference,
            tuple(heuristic_intent.hard_constraints.must_avoid or []),
            tuple(heuristic_intent.soft_preferences.must_include or []),
            heuristic_intent.meal_preferences.meal_count,
            heuristic_intent.meal_preferences.satiety_preference,
            heuristic_intent.meal_preferences.post_workout_meal,
            heuristic_intent.meal_preferences.pre_workout_meal,
        )

        has_clear_override = heuristic_signature != default_signature
        token_count = len(normalized_instruction.split())
        has_explicit_goal = bool(heuristic_intent.goal_raw_semantic)
        has_explicit_constraints = any(
            [
                heuristic_intent.hard_constraints.dietary_preference,
                heuristic_intent.hard_constraints.allergies,
                heuristic_intent.hard_constraints.must_avoid,
                heuristic_intent.soft_preferences.must_include,
                heuristic_intent.meal_preferences.meal_count,
                heuristic_intent.meal_preferences.satiety_preference,
                heuristic_intent.meal_preferences.post_workout_meal,
                heuristic_intent.meal_preferences.pre_workout_meal,
            ]
        )

        if has_explicit_goal and token_count <= 12:
            return True
        if has_explicit_constraints and token_count <= 18 and has_clear_override:
            return True
        return False

    def _should_clarify_for_chat(self, instruction: str, heuristic_intent: NutritionIntent) -> bool:
        raw_goal = heuristic_intent.goal_raw_semantic
        if raw_goal not in CHAT_CLARIFY_GOALS:
            return False

        token_count = len(instruction.split())
        has_specific_context = any(
            [
                heuristic_intent.soft_preferences.must_include,
                heuristic_intent.soft_preferences.preferred_foods,
                heuristic_intent.soft_preferences.disliked_foods,
                heuristic_intent.hard_constraints.must_avoid,
                heuristic_intent.meal_preferences.meal_count,
                heuristic_intent.meal_preferences.satiety_preference,
                heuristic_intent.meal_preferences.pre_workout_meal,
                heuristic_intent.meal_preferences.post_workout_meal,
                heuristic_intent.soft_preferences.cooking_complexity,
                heuristic_intent.soft_preferences.budget_level,
                heuristic_intent.soft_preferences.meal_style,
            ]
        )
        if has_specific_context:
            return False
        if raw_goal == "gain_weight_general" and self._any_phrase_in_text(instruction, ["tap", "gym", "protein", "sau tap", "phuc hoi", "post workout"]):
            return False
        if raw_goal == "lose_weight_general" and self._any_phrase_in_text(instruction, ["giam mo", "no lau", "khong doi", "thanh dam", "it dau mo"]):
            return False
        return token_count <= 10
