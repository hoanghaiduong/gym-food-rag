from __future__ import annotations

import re
from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.services.nutrition_knowledge_service import ascii_normalize, safe_float


class WorkflowValidationMetricsMixin:
    def _pct_error(self, actual: float, target: float) -> float:
        return abs(float(actual) - float(target)) / max(float(target), 1.0)

    @staticmethod
    def _is_plant_based_diet(dietary_preference: Optional[str]) -> bool:
        return (dietary_preference or "").lower() in ("vegetarian", "vegan")

    @staticmethod
    def _diet_aware_tolerances(
        dietary_preference: Optional[str],
        base_calorie_tolerance: float,
        base_macro_tolerance: float,
        budget_level: Optional[str] = None,
    ) -> tuple[float, float]:
        """Return relaxed tolerances for plant-based and budget cases.

        Vegetarian/vegan: calorie +/-12%, macro +/-22%.
        Budget cases: macro +/-0.25 to allow practical options.
        """
        # Inlined check to eliminate any cross-mixin NameError (WorkflowValidationMixin reference removed)
        is_plant_based = (dietary_preference or "").lower() in ("vegetarian", "vegan")
        is_budget = str(budget_level or "").lower() in ("low", "budget")
        if is_plant_based:
            return (
                max(base_calorie_tolerance, 0.12),
                max(base_macro_tolerance, 0.22),
            )
        if is_budget:
            return (
                max(base_calorie_tolerance, 0.12),
                max(base_macro_tolerance, 0.25),
            )
        return base_calorie_tolerance, base_macro_tolerance

    @staticmethod
    def _has_sufficient_protein_density(
        items: list[dict[str, Any]],
        min_density: float = 6.0,
    ) -> bool:
        for item in items:
            protein = safe_float(item.get("protein_g"), 0.0)
            grams = max(safe_float(item.get("grams"), 100.0), 1.0)
            density_per_100g = protein / grams * 100.0
            if density_per_100g >= min_density:
                return True
        return False

    def _validate_role_coverage(
        self,
        goal: str,
        role_counts: dict[str, int],
    ) -> Optional[dict[str, Any]]:
        if goal == "gain_muscle":
            if role_counts["protein"] < 2 or role_counts["carb"] < 2:
                return {
                    "code": "meal_realism_role_coverage",
                    "severity": "error",
                    "message": "The plan lacks enough protein or carbohydrate anchors for a muscle-gain goal.",
                    "details": {"role_counts": role_counts},
                }
        elif goal == "lose_weight":
            if role_counts["protein"] < 2 or role_counts["produce"] < 1:
                return {
                    "code": "meal_realism_role_coverage",
                    "severity": "error",
                    "message": "The plan lacks enough lean protein or produce anchors for a weight-loss goal.",
                    "details": {"role_counts": role_counts},
                }
        else:
            if role_counts["protein"] < 2 or role_counts["carb"] < 1:
                return {
                    "code": "meal_realism_role_coverage",
                    "severity": "error",
                    "message": "The plan lacks balanced protein and staple carbohydrate anchors.",
                    "details": {"role_counts": role_counts},
                }
        return None
