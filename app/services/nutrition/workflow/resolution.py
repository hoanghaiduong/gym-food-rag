from __future__ import annotations

from typing import Any

from app.services.nutrition_knowledge_service import safe_float

from .strings_vi import INVALID_MODEL_OUTPUT_SUMMARY


class WorkflowResolutionMixin:
    def _safe_parse_plan(self, raw_text: str) -> dict[str, Any]:
        try:
            parsed = self.llm.parse_json(raw_text)
            return parsed if isinstance(parsed, dict) else {"summary": "", "reasoning": [], "meals": []}
        except Exception as exc:
            return {
                "summary": INVALID_MODEL_OUTPUT_SUMMARY,
                "reasoning": [str(exc)],
                "meals": [],
            }

    def _resolve_plan(
        self,
        plan_json: dict[str, Any],
        candidates: list[dict[str, Any]],
        *,
        allow_global_lookup: bool,
    ) -> dict[str, Any]:
        candidate_map = {item["entity_id"]: item for item in candidates}
        totals = {"energy_kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        resolved_meals = []

        for meal in plan_json.get("meals", []) if isinstance(plan_json.get("meals"), list) else []:
            meal_totals = {"energy_kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
            resolved_items = []
            for raw_item in meal.get("items", []) if isinstance(meal.get("items"), list) else []:
                grams = int(round(safe_float(raw_item.get("grams"), 0)))
                food_ref = self.knowledge.resolve_food_reference(
                    entity_id=raw_item.get("entity_id"),
                    food_name=raw_item.get("food_name") or raw_item.get("name"),
                    candidate_map=candidate_map,
                    allow_global_lookup=allow_global_lookup,
                    allow_blocked_lookup=True,
                )
                substituted_from = None
                substitution_applied = False
                if food_ref and food_ref.get("final_output_allowed") is False:
                    safe_sibling = self.knowledge.find_safe_sibling(
                        food_ref=food_ref,
                        candidate_map=candidate_map,
                    )
                    if safe_sibling:
                        substituted_from = {
                            "entity_id": food_ref.get("entity_id"),
                            "name": food_ref.get("name"),
                        }
                        food_ref = safe_sibling
                        substitution_applied = True
                if food_ref:
                    factor = max(grams, 0) / 100.0
                    display_name = food_ref.get("safe_display_name") or food_ref["name"]
                    resolved_item = {
                        "entity_id": food_ref["entity_id"],
                        "source_food_name": substituted_from["name"] if substituted_from else food_ref["name"],
                        "food_name": display_name,
                        "food_id": food_ref.get("food_id"),
                        "grams": grams,
                        "reason": raw_item.get("reason"),
                        "group_name": food_ref.get("group_name"),
                        "image_url": food_ref.get("image_url"),
                        "image_source_url": food_ref.get("image_source_url"),
                        "energy_kcal": round(food_ref["energy_kcal"] * factor, 1),
                        "protein_g": round(food_ref["protein_g"] * factor, 1),
                        "carbs_g": round(food_ref["carbs_g"] * factor, 1),
                        "fat_g": round(food_ref["fat_g"] * factor, 1),
                        "allergen_tags": food_ref.get("allergen_tags") or [],
                        "diet_tags": food_ref.get("diet_tags") or [],
                        "meal_readiness_tier": food_ref.get("meal_readiness_tier"),
                        "meal_role_tags": food_ref.get("meal_role_tags") or [],
                        "planner_rank_weight": food_ref.get("planner_rank_weight"),
                        "consumption_state": food_ref.get("consumption_state"),
                        "final_output_allowed": food_ref.get("final_output_allowed"),
                        "unsafe_output_reason": food_ref.get("unsafe_output_reason"),
                        "safe_display_name": display_name,
                        "preparation_style": food_ref.get("preparation_style"),
                        "ingredient_hints": food_ref.get("ingredient_hints") or [],
                        "source_url": food_ref.get("source_url"),
                        "substituted_to_safe_variant": substitution_applied,
                        "substituted_from_entity_id": substituted_from["entity_id"] if substituted_from else None,
                        "substituted_from_name": substituted_from["name"] if substituted_from else None,
                        "resolved": True,
                    }
                else:
                    resolved_item = {
                        "entity_id": raw_item.get("entity_id"),
                        "source_food_name": raw_item.get("source_food_name") or raw_item.get("food_name") or raw_item.get("name"),
                        "food_name": raw_item.get("food_name") or raw_item.get("name") or "Unknown",
                        "food_id": None,
                        "grams": grams,
                        "reason": raw_item.get("reason"),
                        "group_name": None,
                        "image_url": None,
                        "image_source_url": None,
                        "energy_kcal": 0.0,
                        "protein_g": 0.0,
                        "carbs_g": 0.0,
                        "fat_g": 0.0,
                        "allergen_tags": [],
                        "diet_tags": [],
                        "meal_readiness_tier": None,
                        "meal_role_tags": [],
                        "planner_rank_weight": None,
                        "consumption_state": None,
                        "final_output_allowed": None,
                        "unsafe_output_reason": None,
                        "safe_display_name": None,
                        "preparation_style": None,
                        "ingredient_hints": [],
                        "source_url": None,
                        "substituted_to_safe_variant": False,
                        "substituted_from_entity_id": None,
                        "substituted_from_name": None,
                        "resolved": False,
                    }

                resolved_items.append(resolved_item)
                for key in meal_totals:
                    meal_totals[key] += resolved_item[key]

            resolved_meals.append(
                {
                    "meal_name": meal.get("meal_name", "Meal"),
                    "explanation": meal.get("explanation", ""),
                    "items": resolved_items,
                    "totals": {key: round(value, 1) for key, value in meal_totals.items()},
                }
            )
            for key in totals:
                totals[key] += meal_totals[key]

        return {
            "summary": str(plan_json.get("summary") or ""),
            "reasoning": [str(item) for item in plan_json.get("reasoning", []) if isinstance(item, str)],
            "meals": resolved_meals,
            "totals": {key: round(value, 1) for key, value in totals.items()},
        }

    def _strip_to_structured_plan(self, resolved_plan: dict[str, Any]) -> dict[str, Any]:
        meals = []
        for meal in resolved_plan.get("meals", []):
            meals.append(
                {
                    "meal_name": meal["meal_name"],
                    "explanation": meal["explanation"],
                    "items": [
                        {
                            "entity_id": item.get("entity_id"),
                            "food_name": item.get("food_name"),
                            "grams": item.get("grams"),
                            "reason": item.get("reason"),
                        }
                        for item in meal.get("items", [])
                    ],
                }
            )
        return {
            "summary": resolved_plan.get("summary") or "",
            "reasoning": resolved_plan.get("reasoning") or [],
            "meals": meals,
        }
