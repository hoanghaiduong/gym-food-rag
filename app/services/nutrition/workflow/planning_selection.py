from __future__ import annotations

import json
from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import safe_float
from app.services.nutrition_service import NutritionService

from .constants import GOAL_POOL_RULES


class WorkflowPlanningSelectionMixin:
    def _select_rule_based_candidates(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        candidates: list[dict[str, Any]],
        intent: Optional[NutritionIntent] = None,
    ) -> list[dict[str, Any]]:
        goal = self._resolve_goal_family(profile, intent)
        rules = GOAL_POOL_RULES.get(goal, GOAL_POOL_RULES["maintain"]).copy()
        # ⭐ Boost produce/post-workout for deficit cases to hit >95% recall (consistent with optimize pool)
        is_post_workout = bool(intent and getattr(intent.meal_preferences, "post_workout_meal", False))
        if goal in ("lose_weight", "deficit_balanced", "deficit_high_satiety") or is_post_workout:
            rules["produce_anchor_count"] = 5
            rules["protein_anchor_count"] = max(rules.get("protein_anchor_count", 3), 4)
        if self._is_plant_based_diet(profile.get("dietary_preference")):
            rules["protein_anchor_count"] = max(rules["protein_anchor_count"], 5)
            rules["healthy_fat_anchor_count"] = max(rules.get("healthy_fat_anchor_count", 0), 3)
        ranked = self._sort_candidates_for_goal(candidates, profile, request, intent)
        ranked = self._filter_candidates_for_meal_planning(ranked, profile, request, intent)

        selected: list[dict[str, Any]] = []
        must_include_matches = self._collect_must_include_candidates(ranked, request)
        protein_bucket = [item for item in ranked if self._candidate_role(item, goal) == "protein"]
        carb_bucket = [item for item in ranked if self._candidate_role(item, goal) == "carb"]
        produce_bucket = [item for item in ranked if self._candidate_role(item, goal) == "produce"]
        balanced_bucket = [
            item for item in ranked if self._candidate_role(item, goal) in {"balanced", "fat"}
        ]
        healthy_fat_bucket = self._healthy_fat_candidates(ranked, goal)

        pool_limit = max(request.top_k, rules["pool_limit"])
        self._take_unique_candidates(selected, must_include_matches, count=min(pool_limit, max(len(request.must_include), 2)))
        self._take_unique_candidates(
            selected,
            protein_bucket,
            count=min(pool_limit, len(selected) + rules["protein_anchor_count"]),
        )
        self._take_unique_candidates(
            selected,
            carb_bucket,
            count=min(pool_limit, len(selected) + rules["carb_anchor_count"]),
        )
        if goal == "lose_weight":
            self._take_unique_candidates(
                selected,
                produce_bucket,
                count=min(pool_limit, len(selected) + rules["produce_anchor_count"]),
            )
        self._take_unique_candidates(
            selected,
            healthy_fat_bucket,
            count=min(pool_limit, len(selected) + rules.get("healthy_fat_anchor_count", 0)),
        )
        if goal != "lose_weight":
            self._take_unique_candidates(
                selected,
                produce_bucket,
                count=min(pool_limit, len(selected) + rules["produce_anchor_count"]),
            )
        self._take_unique_candidates(
            selected,
            balanced_bucket,
            count=min(pool_limit, len(selected) + rules["balanced_anchor_count"]),
        )
        self._take_unique_candidates(selected, ranked, count=pool_limit)
        return selected

    def _build_meal_candidate_subset(
        self,
        meal_index: int,
        goal: str,
        selected_candidates: list[dict[str, Any]],
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent] = None,
    ) -> list[dict[str, Any]]:
        protein_bucket = [item for item in selected_candidates if self._candidate_role(item, goal) == "protein"]
        carb_bucket = [item for item in selected_candidates if self._candidate_role(item, goal) == "carb"]
        produce_bucket = [item for item in selected_candidates if self._candidate_role(item, goal) == "produce"]
        balanced_bucket = [
            item for item in selected_candidates if self._candidate_role(item, goal) in {"balanced", "fat"}
        ]
        healthy_fat_bucket = self._healthy_fat_candidates(selected_candidates, goal)
        must_include_matches = [
            item for item in selected_candidates if any(self._candidate_matches_hint(item, hint) for hint in request.must_include)
        ]

        subset: list[dict[str, Any]] = []
        if must_include_matches:
            subset.append(must_include_matches[meal_index % len(must_include_matches)])
        if protein_bucket:
            subset.append(protein_bucket[meal_index % len(protein_bucket)])
        if goal == "gain_muscle" and len(protein_bucket) > 1:
            subset.append(protein_bucket[(meal_index + 1) % len(protein_bucket)])
        if carb_bucket:
            subset.append(carb_bucket[meal_index % len(carb_bucket)])
        if goal == "gain_muscle" and len(carb_bucket) > 1 and meal_index < 2:
            subset.append(carb_bucket[(meal_index + 1) % len(carb_bucket)])
        if goal != "gain_muscle" and produce_bucket:
            subset.append(produce_bucket[meal_index % len(produce_bucket)])
        elif goal == "gain_muscle" and produce_bucket and meal_index in {0, 2}:
            subset.append(produce_bucket[meal_index % len(produce_bucket)])
        if goal in {"lose_weight", "maintain"} and healthy_fat_bucket:
            subset.append(healthy_fat_bucket[meal_index % len(healthy_fat_bucket)])
        if balanced_bucket:
            subset.append(balanced_bucket[meal_index % len(balanced_bucket)])

        deduped: list[dict[str, Any]] = []
        self._take_unique_candidates(deduped, subset, count=6 if goal == "gain_muscle" else 5)
        if intent and intent.soft_preferences.preferred_foods:
            preferred_matches = [
                item
                for item in selected_candidates
                if any(self._candidate_matches_hint(item, hint) for hint in intent.soft_preferences.preferred_foods)
            ]
            self._take_unique_candidates(deduped, preferred_matches, count=6 if goal == "gain_muscle" else 5)
        if len(deduped) < 4:
            self._take_unique_candidates(deduped, selected_candidates, count=5)
        return deduped

    def _build_daily_optimization_subset(
        self,
        goal: str,
        selected_candidates: list[dict[str, Any]],
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent] = None,
    ) -> list[dict[str, Any]]:
        protein_bucket = [item for item in selected_candidates if self._candidate_role(item, goal) == "protein"]
        carb_bucket = [item for item in selected_candidates if self._candidate_role(item, goal) == "carb"]
        produce_bucket = [item for item in selected_candidates if self._candidate_role(item, goal) == "produce"]
        balanced_bucket = [
            item for item in selected_candidates if self._candidate_role(item, goal) in {"balanced", "fat"}
        ]
        healthy_fat_bucket = self._healthy_fat_candidates(selected_candidates, goal)
        must_include_matches = [
            item for item in selected_candidates if any(self._candidate_matches_hint(item, hint) for hint in request.must_include)
        ]

        subset: list[dict[str, Any]] = []
        if must_include_matches:
            self._take_unique_candidates(subset, must_include_matches, count=min(len(request.must_include), 2))

        if goal == "gain_muscle":
            self._take_unique_candidates(subset, protein_bucket, count=len(subset) + 3)
            self._take_unique_candidates(subset, carb_bucket, count=len(subset) + 3)
            self._take_unique_candidates(subset, healthy_fat_bucket, count=len(subset) + 2)
            self._take_unique_candidates(subset, produce_bucket, count=len(subset) + 2)
            self._take_unique_candidates(subset, balanced_bucket, count=len(subset) + 1)
        elif goal == "lose_weight":
            self._take_unique_candidates(subset, protein_bucket, count=len(subset) + 3)
            self._take_unique_candidates(subset, carb_bucket, count=len(subset) + 2)
            self._take_unique_candidates(subset, healthy_fat_bucket, count=len(subset) + 2)
            self._take_unique_candidates(subset, produce_bucket, count=len(subset) + 2)
            self._take_unique_candidates(subset, balanced_bucket, count=len(subset) + 1)
        else:
            self._take_unique_candidates(subset, protein_bucket, count=len(subset) + 3)
            self._take_unique_candidates(subset, carb_bucket, count=len(subset) + 2)
            self._take_unique_candidates(subset, healthy_fat_bucket, count=len(subset) + 1)
            self._take_unique_candidates(subset, produce_bucket, count=len(subset) + 2)
            self._take_unique_candidates(subset, balanced_bucket, count=len(subset) + 2)

        if intent and intent.soft_preferences.preferred_foods:
            preferred_matches = [
                item
                for item in selected_candidates
                if any(self._candidate_matches_hint(item, hint) for hint in intent.soft_preferences.preferred_foods)
            ]
            self._take_unique_candidates(subset, preferred_matches, count=len(subset) + 2)

        self._take_unique_candidates(subset, selected_candidates, count=min(len(selected_candidates), 10))
        return subset
