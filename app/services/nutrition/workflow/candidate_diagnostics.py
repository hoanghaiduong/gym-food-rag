from __future__ import annotations

from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent

from .models import CandidateDiagnostics, WorkflowTargets


class WorkflowCandidateDiagnosticsMixin:
    def _candidate_diagnostics(
        self,
        candidates: list[dict[str, Any]],
        request: NutritionRecommendationRequest,
        targets: WorkflowTargets,
        profile: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> CandidateDiagnostics:
        goal = self._resolve_goal_family(profile, intent)
        role_counts = {"protein": 0, "carb": 0, "produce": 0, "balanced": 0, "fat": 0}
        for item in candidates:
            role_counts[self._candidate_role(item, goal)] += 1
        return {
            "goal": goal,
            "planning_strategy": self._resolve_planning_strategy(profile, intent),
            "candidate_count": len(candidates),
            "role_counts": role_counts,
            "must_include_hits": {
                item: any(self._candidate_matches_hint(candidate, item) for candidate in candidates)
                for item in request.must_include
            },
            "preferred_food_hits": {
                item: any(self._candidate_matches_hint(candidate, item) for candidate in candidates)
                for item in (intent.soft_preferences.preferred_foods if intent else [])
            },
            "top_candidates": [candidate.get("name") for candidate in candidates[:8]],
            "target_calories": targets.get("daily_calories"),
            "intent_summary": intent.model_dump(mode="json") if intent else None,
        }

    def _format_candidate_anchor_summary(
        self,
        profile: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> str:
        goal = self._resolve_goal_family(profile)
        protein_bucket = [item["name"] for item in candidates if self._candidate_role(item, goal) == "protein"][:4]
        carb_bucket = [item["name"] for item in candidates if self._candidate_role(item, goal) == "carb"][:4]
        produce_bucket = [item["name"] for item in candidates if self._candidate_role(item, goal) == "produce"][:3]
        balanced_bucket = [
            item["name"]
            for item in candidates
            if self._candidate_role(item, goal) in {"balanced", "fat"}
        ][:4]
        return "\n".join(
            [
                f"- protein anchors: {protein_bucket or ['none']}",
                f"- carb anchors: {carb_bucket or ['none']}",
                f"- produce/support: {produce_bucket or ['none']}",
                f"- balanced/fat support: {balanced_bucket or ['none']}",
            ]
        )
