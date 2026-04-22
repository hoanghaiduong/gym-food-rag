from __future__ import annotations

from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize

from .constants import (
    DIET_RETRIEVAL_PROTEIN_HINTS,
    GENERIC_SUPPORT_HINTS,
    HEALTHY_BALANCED_MEAL_PHRASES,
    RETRIEVAL_ALLERGY_ANCHOR_BLOCKLIST,
    RETRIEVAL_BALANCED_ANCHORS,
    RETRIEVAL_EXPECTED_ROLE_TAGS,
    RETRIEVAL_QUERY_STOPWORDS,
    RETRIEVAL_SHARED_ANCHORS,
    RETRIEVAL_STRATEGY_DIET_ANCHORS,
)


class WorkflowRetrievalContextMixin:
    def _prioritize_retrieval_terms(self, values: list[str], *, limit: Optional[int] = None) -> list[str]:
        prioritized = self._unique_retrieval_terms(values)
        prioritized.sort(
            key=lambda value: (
                ascii_normalize(value or "") in GENERIC_SUPPORT_HINTS,
                -len(ascii_normalize(value or "").split()),
                -len(ascii_normalize(value or "")),
            )
        )
        if limit is not None:
            return prioritized[:limit]
        return prioritized

    def _intent_priority_tokens(self, intent: Optional[NutritionIntent]) -> set[str]:
        if intent is None:
            return set()
        return {
            ascii_normalize(str(item or "")).replace(" ", "_")
            for item in (intent.priorities or [])
            if ascii_normalize(str(item or ""))
        }

    def _is_health_support_retrieval_intent(self, intent: Optional[NutritionIntent]) -> bool:
        if intent is None:
            return False

        planning_strategy = self._normalize_planning_strategy(getattr(intent, "planning_strategy", None))
        if planning_strategy == "maintenance_health_support":
            return True
        if planning_strategy not in {None, "maintenance_balanced"}:
            return False

        priorities = self._intent_priority_tokens(intent)
        meal_style = ascii_normalize(intent.soft_preferences.meal_style or "").replace(" ", "_")
        satiety_preference = ascii_normalize(intent.meal_preferences.satiety_preference or "").replace(" ", "_")

        return bool(
            priorities & {"micronutrients", "lightness", "digestion"}
            or meal_style == "light"
            or satiety_preference == "light"
        )

    def _resolve_retrieval_strategy(
        self,
        profile: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> str:
        strategy = self._resolve_planning_strategy(profile, intent) or "maintenance_balanced"
        if strategy == "maintenance_balanced" and self._is_health_support_retrieval_intent(intent):
            return "maintenance_health_support"
        return strategy

    def _unique_retrieval_terms(self, values: list[str], *, limit: Optional[int] = None) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = ascii_normalize(value or "")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
            if limit is not None and len(unique) >= limit:
                break
        return unique

    def _prune_anchor_terms_for_allergies(self, terms: list[str], allergy_tags: list[str]) -> list[str]:
        blocked_terms = set()
        for allergy in allergy_tags:
            blocked_terms.update(RETRIEVAL_ALLERGY_ANCHOR_BLOCKLIST.get(allergy, set()))
        if not blocked_terms:
            return self._unique_retrieval_terms(terms)

        filtered: list[str] = []
        for term in self._unique_retrieval_terms(terms):
            if any(
                blocked
                and (
                    blocked == term
                    or blocked in term
                    or (len(blocked.split()) == 1 and blocked in set(term.split()))
                )
                for blocked in blocked_terms
            ):
                continue
            filtered.append(term)
        return filtered

    def _compact_instruction_for_retrieval(self, instruction: str, *, limit: int = 8) -> str:
        tokens = [
            token
            for token in ascii_normalize(instruction or "").split()
            if len(token) >= 2 and token not in RETRIEVAL_QUERY_STOPWORDS
        ]
        compact_tokens: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            compact_tokens.append(token)
            if len(compact_tokens) >= limit:
                break
        return " ".join(compact_tokens)

    def _build_retrieval_rerank_context(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent] = None,
    ) -> dict[str, Any]:
        planning_strategy = self._resolve_retrieval_strategy(profile, intent)
        goal = self._resolve_goal_family(profile, intent)
        diet = profile.get("dietary_preference") or "omnivore"
        allergy_tags = list(profile.get("allergy_tags") or [])
        strategy_anchor_map = (
            RETRIEVAL_STRATEGY_DIET_ANCHORS.get(planning_strategy)
            or RETRIEVAL_STRATEGY_DIET_ANCHORS["maintenance_balanced"]
        )
        diet_anchor_map = strategy_anchor_map.get(diet) or strategy_anchor_map.get("omnivore") or {}
        protein_anchors = self._prune_anchor_terms_for_allergies(diet_anchor_map.get("protein") or [], allergy_tags)
        protein_anchors = self._unique_retrieval_terms(
            [
                *self._prune_anchor_terms_for_allergies(
                    DIET_RETRIEVAL_PROTEIN_HINTS.get(diet) or [],
                    allergy_tags,
                ),
                *protein_anchors,
            ],
            limit=5,
        )
        carb_anchors = self._prune_anchor_terms_for_allergies(RETRIEVAL_SHARED_ANCHORS["carb"], allergy_tags)
        produce_anchors = self._prune_anchor_terms_for_allergies(RETRIEVAL_SHARED_ANCHORS["produce"], allergy_tags)
        balanced_anchors = self._prune_anchor_terms_for_allergies(
            (diet_anchor_map.get("balanced") or RETRIEVAL_BALANCED_ANCHORS.get(diet) or []),
            allergy_tags,
        )
        must_include = self._prioritize_retrieval_terms(
            [
                *(request.must_include or []),
                *((intent.soft_preferences.must_include or []) if intent else []),
            ],
            limit=6,
        )
        prioritized_protein_hints = [
            item for item in must_include if item in set(protein_anchors) or item in set(balanced_anchors)
        ]
        prioritized_carb_hints = [item for item in must_include if item in set(carb_anchors)]
        prioritized_produce_hints = [item for item in must_include if item in set(produce_anchors)]
        protein_anchors = self._unique_retrieval_terms([*prioritized_protein_hints, *protein_anchors], limit=4)
        carb_anchors = self._unique_retrieval_terms([*prioritized_carb_hints, *carb_anchors], limit=4)
        produce_anchors = self._unique_retrieval_terms([*prioritized_produce_hints, *produce_anchors], limit=4)
        balanced_anchors = self._unique_retrieval_terms([*prioritized_protein_hints, *balanced_anchors], limit=4)
        preferred_foods = self._prioritize_retrieval_terms(
            list((intent.soft_preferences.preferred_foods or []) if intent else []),
            limit=4,
        )
        balanced_meal_required = self._requires_balanced_health_bias(
            request,
            intent,
            planning_strategy,
        )
        post_workout_meal = bool(intent.meal_preferences.post_workout_meal) if intent else False
        expected_role_tags = list(
            RETRIEVAL_EXPECTED_ROLE_TAGS.get(
                planning_strategy,
                RETRIEVAL_EXPECTED_ROLE_TAGS["maintenance_balanced"],
            )
        )
        if balanced_meal_required:
            expected_role_tags = self._unique_retrieval_terms(
                ["protein_anchor", "carb_anchor", "produce_support", *expected_role_tags],
                limit=4,
            )
        if post_workout_meal:
            # Ensure post_workout_friendly is rewarded in role_alignment_score for
            # cases like deficit_balanced + post-workout style (e.g. retrieval_reco_065)
            expected_role_tags = self._unique_retrieval_terms(
                [*expected_role_tags, "post_workout_friendly"],
                limit=5,
            )
        anchor_terms = self._prioritize_retrieval_terms(
            [*must_include, *preferred_foods, *protein_anchors, *carb_anchors, *balanced_anchors, *produce_anchors],
            limit=12,
        )
        return {
            "goal": goal,
            "planning_strategy": planning_strategy,
            "dietary_preference": diet,
            "must_include": must_include,
            "preferred_foods": preferred_foods,
            "excluded_foods": self._unique_retrieval_terms(list(request.excluded_foods or []), limit=4),
            "allergy_tags": allergy_tags,
            "expected_role_tags": expected_role_tags,
            "anchor_terms": anchor_terms,
            "protein_anchors": protein_anchors,
            "carb_anchors": carb_anchors,
            "produce_anchors": produce_anchors,
            "balanced_anchors": balanced_anchors,
            "post_workout_meal": post_workout_meal,
            "pre_workout_meal": bool(intent.meal_preferences.pre_workout_meal) if intent else False,
            "satiety_preference": intent.meal_preferences.satiety_preference if intent else None,
            "balanced_meal_required": balanced_meal_required,
        }

    def _requires_balanced_health_bias(
        self,
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent],
        planning_strategy: Optional[str],
    ) -> bool:
        strategy = self._normalize_planning_strategy(planning_strategy)
        if strategy not in {"maintenance_balanced", "maintenance_health_support"}:
            return False
        if self._is_health_support_retrieval_intent(intent):
            return True

        normalized_instruction = ascii_normalize(request.instruction or "")
        if any(phrase in normalized_instruction for phrase in HEALTHY_BALANCED_MEAL_PHRASES):
            return True
        if intent and ascii_normalize(intent.goal_raw_semantic or "").replace(" ", "_") == "eat_healthier":
            return True
        return False
