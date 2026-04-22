from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.ollama_nutrition_service import ollama_nutrition_service

from .heuristics import IntentHeuristicsMixin
from .merging import IntentMergingMixin
from .normalization import IntentNormalizationMixin
from .prompts import IntentPromptMixin
from .taxonomy import CHAT_CLARIFY_GOALS


class NutritionIntentService(
    IntentNormalizationMixin,
    IntentHeuristicsMixin,
    IntentPromptMixin,
    IntentMergingMixin,
):
    version = "intent_parser_v4"
    CHAT_CLARIFY_GOALS = CHAT_CLARIFY_GOALS

    def __init__(self):
        self.llm = ollama_nutrition_service

    def parse_intent(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> NutritionIntent:
        default_intent = self._build_default_intent(profile, request)
        instruction = (request.instruction or "").strip()
        if not instruction:
            return default_intent

        heuristic_intent = self._build_heuristic_intent(profile, request)
        merged_intent = self._merge_intents(default_intent, heuristic_intent)
        if self._should_short_circuit_llm(
            instruction=instruction,
            default_intent=default_intent,
            heuristic_intent=heuristic_intent,
        ):
            merged_intent.source = "heuristic_short_circuit"
            merged_intent.dietary_override = self._detect_dietary_override(profile, request, merged_intent)
            return merged_intent

        try:
            raw_text = self.llm.generate_text(self._build_prompt(profile, request, merged_intent), temperature=0.0)
            parsed_payload = self.llm.parse_json(raw_text)
            llm_intent = self._normalize_payload(parsed_payload, source="llm_semantic_parser")
            final_intent = self._merge_intents(merged_intent, llm_intent)
            final_intent = self._prefer_more_specific_goal(
                default_intent=default_intent,
                heuristic_intent=heuristic_intent,
                llm_intent=llm_intent,
                final_intent=final_intent,
            )
            final_intent = self._prefer_explicit_heuristic_constraints(
                heuristic_intent=heuristic_intent,
                final_intent=final_intent,
            )
            final_intent.dietary_override = self._detect_dietary_override(profile, request, final_intent)
            return final_intent
        except Exception as exc:
            fallback = merged_intent.model_copy(deep=True)
            fallback.source = "heuristic_fallback"
            fallback.notes = self._merge_list(fallback.notes, [f"semantic_parser_fallback:{exc.__class__.__name__}"])
            fallback.dietary_override = self._detect_dietary_override(profile, request, fallback)
            return fallback

    def get_chat_clarification(self, profile: dict[str, Any], instruction: str) -> dict[str, Any] | None:
        request = NutritionRecommendationRequest(instruction=instruction)
        default_intent = self._build_default_intent(profile, request)
        heuristic_intent = self._build_heuristic_intent(profile, request)
        merged_intent = self._merge_intents(default_intent, heuristic_intent)
        normalized_instruction = self._normalize_instruction(instruction)

        if not self._should_clarify_for_chat(normalized_instruction, heuristic_intent):
            return None

        raw_goal = heuristic_intent.goal_raw_semantic
        question = self._build_chat_clarification_question(raw_goal)
        if not question:
            return None

        return {
            "needed": True,
            "reason": self.CHAT_CLARIFY_GOALS.get(raw_goal, "clarify_intent"),
            "question": question,
            "intent_preview": {
                "goal_raw_semantic": merged_intent.goal_raw_semantic,
                "goal_normalized_internal": merged_intent.goal_normalized_internal or merged_intent.goal,
                "planning_strategy": merged_intent.planning_strategy,
            },
        }

    def apply_to_profile(self, profile: dict[str, Any], intent: NutritionIntent) -> dict[str, Any]:
        effective_profile = deepcopy(profile)
        internal_goal = intent.goal_normalized_internal or intent.goal
        if internal_goal:
            effective_profile["target_goal"] = internal_goal
            effective_profile["goal_normalized_internal"] = internal_goal
        if intent.goal_raw_semantic:
            effective_profile["goal_raw_semantic"] = intent.goal_raw_semantic
        if intent.planning_strategy:
            effective_profile["planning_strategy"] = intent.planning_strategy
        if intent.hard_constraints.dietary_preference:
            effective_profile["dietary_preference"] = intent.hard_constraints.dietary_preference

        effective_profile["dietary_override"] = intent.dietary_override

        allergy_tags = self._merge_list(effective_profile.get("allergy_tags") or [], intent.hard_constraints.allergies)
        effective_profile["allergy_tags"] = allergy_tags
        effective_profile["allergies"] = ", ".join(allergy_tags) if allergy_tags else None
        return effective_profile

    def apply_to_request(
        self,
        request: NutritionRecommendationRequest,
        intent: NutritionIntent,
    ) -> NutritionRecommendationRequest:
        meal_count = intent.meal_preferences.meal_count or request.meal_count
        must_include = self._merge_list(request.must_include, intent.soft_preferences.must_include)
        excluded_foods = self._merge_list(request.excluded_foods, intent.hard_constraints.must_avoid + intent.soft_preferences.disliked_foods)
        return request.model_copy(update={"meal_count": meal_count, "must_include": must_include, "excluded_foods": excluded_foods})


nutrition_intent_service = NutritionIntentService()
