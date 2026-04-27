from __future__ import annotations

from typing import Any

from app.schemas.nutrition import NutritionRecommendationRequest
from app.services.nutrition_knowledge_service import safe_float


class WorkflowPlanningMacroClosureMixin:
    def _repair_meal_plan_macro_balance(
        self,
        *,
        goal: str,
        meals: list[dict[str, Any]],
        candidate_pool: list[dict[str, Any]],
        targets: dict[str, Any],
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> list[dict[str, Any]]:
        repaired = super()._repair_meal_plan_macro_balance(
            goal=goal,
            meals=meals,
            candidate_pool=candidate_pool,
            targets=targets,
            profile=profile,
            request=request,
        )
        return self._close_under_target_macros(
            goal=goal,
            meals=repaired,
            candidate_pool=candidate_pool,
            targets=targets,
            profile=profile,
            request=request,
        )

    def _close_under_target_macros(
        self,
        *,
        goal: str,
        meals: list[dict[str, Any]],
        candidate_pool: list[dict[str, Any]],
        targets: dict[str, Any],
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> list[dict[str, Any]]:
        candidate_lookup = {
            candidate.get("entity_id"): candidate
            for candidate in candidate_pool
            if candidate.get("entity_id")
        }
        hydrated_candidate_pool = list(candidate_pool)
        resolver = getattr(getattr(self, "knowledge", None), "resolve_food_reference", None)
        if resolver is not None:
            for meal in meals:
                for item in meal.get("items", []):
                    entity_id = item.get("entity_id")
                    if not entity_id or entity_id in candidate_lookup:
                        continue
                    resolved = resolver(
                        entity_id=entity_id,
                        food_name=item.get("food_name"),
                        candidate_map=candidate_lookup,
                        allow_global_lookup=True,
                        allow_blocked_lookup=False,
                    )
                    if resolved is None:
                        continue
                    if resolved.get("final_output_allowed") is False:
                        continue
                    if resolved.get("consumption_state") == "requires_preparation":
                        continue
                    candidate_lookup[entity_id] = resolved
                    hydrated_candidate_pool.append(resolved)
        candidate_pool = hydrated_candidate_pool
        if not candidate_lookup:
            return meals

        calorie_tolerance = max(float(request.calorie_tolerance_pct or 0.0), 0.0)
        macro_tolerance = max(float(request.macro_tolerance_pct or 0.0), 0.0)
        energy_lower = safe_float(targets.get("daily_calories"), 0.0) * (1.0 - calorie_tolerance)
        energy_upper = safe_float(targets.get("daily_calories"), 0.0) * (1.0 + calorie_tolerance)
        macro_lowers = {
            key: safe_float(targets.get(key), 0.0) * (1.0 - macro_tolerance)
            for key in ("protein_g", "carbs_g", "fat_g")
        }

        def totals() -> dict[str, float]:
            values = {"energy_kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
            for meal in meals:
                for item in meal.get("items", []):
                    candidate = candidate_lookup.get(item.get("entity_id"))
                    if candidate is None:
                        continue
                    grams = max(safe_float(item.get("grams"), 0.0), 0.0)
                    factor = grams / 100.0
                    for key in values:
                        values[key] += safe_float(candidate.get(key), 0.0) * factor
            return values

        def item_grams(item: dict[str, Any]) -> int:
            return max(int(round(safe_float(item.get("grams"), 0.0))), 0)

        def set_item_grams(item: dict[str, Any], grams: float) -> None:
            item["grams"] = max(30, int(round(grams)))

        def macro_portion_cap(candidate: dict[str, Any], meal_name: str) -> int:
            cap = self._portion_cap_for_candidate(candidate, goal, meal_name)
            if goal == "gain_muscle" and self._is_healthy_fat_support(candidate, goal):
                return max(cap, 60)
            if goal == "maintain" and self._is_healthy_fat_support(candidate, goal):
                return max(cap, 60 if self._is_main_meal_name(meal_name) else 45)
            if goal == "lose_weight" and self._is_healthy_fat_support(candidate, goal):
                return max(cap, 60 if self._is_main_meal_name(meal_name) else 45)
            return cap

        def macro_lower_bound(nutrient_key: str, target_ratio: float | None = None) -> float:
            lower_bound = macro_lowers.get(nutrient_key, energy_lower)
            if target_ratio is None:
                return lower_bound
            target_value = safe_float(targets.get(nutrient_key), 0.0)
            if target_value <= 0:
                return lower_bound
            return max(lower_bound, target_value * target_ratio)

        def increase_existing_for(
            nutrient_key: str,
            roles: set[str],
            max_rounds: int = 3,
            target_ratio: float | None = None,
        ) -> None:
            for _ in range(max_rounds):
                current = totals()
                lower_bound = macro_lower_bound(nutrient_key, target_ratio)
                gap = lower_bound - current.get(nutrient_key, 0.0)
                if gap <= 0:
                    return
                energy_room = max(energy_upper - current["energy_kcal"], 0.0)
                if nutrient_key != "energy_kcal" and energy_room <= 20:
                    return
                entries: list[tuple[float, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
                for meal in meals:
                    for item in meal.get("items", []):
                        candidate = candidate_lookup.get(item.get("entity_id"))
                        if candidate is None:
                            continue
                        role = self._candidate_role(candidate, goal)
                        if role not in roles:
                            continue
                        room = macro_portion_cap(candidate, meal.get("meal_name", "")) - item_grams(item)
                        if room <= 0:
                            continue
                        nutrient_density = safe_float(candidate.get(nutrient_key), 0.0)
                        energy_density = safe_float(candidate.get("energy_kcal"), 0.0)
                        if nutrient_density <= 0 or energy_density <= 0:
                            continue
                        entries.append((nutrient_density / max(energy_density, 1.0), meal, item, candidate))
                if not entries:
                    return
                changed = False
                for _score, meal, item, candidate in sorted(
                    entries,
                    key=lambda entry: entry[0],
                    reverse=True,
                ):
                    current = totals()
                    lower_bound = macro_lower_bound(nutrient_key, target_ratio)
                    gap = lower_bound - current.get(nutrient_key, 0.0)
                    if gap <= 0:
                        return
                    energy_room = max(energy_upper - current["energy_kcal"], 0.0)
                    if nutrient_key != "energy_kcal" and energy_room <= 20:
                        return
                    nutrient_per_g = safe_float(candidate.get(nutrient_key), 0.0) / 100.0
                    energy_per_g = safe_float(candidate.get("energy_kcal"), 0.0) / 100.0
                    room = macro_portion_cap(candidate, meal.get("meal_name", "")) - item_grams(item)
                    delta_by_nutrient = gap / max(nutrient_per_g, 0.01)
                    delta_by_energy = energy_room / max(energy_per_g, 0.01)
                    minimum_delta = 1.0 if nutrient_key in {"fat_g", "carbs_g"} else 5.0
                    delta = min(room, max(minimum_delta, delta_by_nutrient), delta_by_energy)
                    if delta < minimum_delta:
                        continue
                    set_item_grams(item, item_grams(item) + delta)
                    changed = True
                if not changed:
                    return

        def add_support_for(nutrient_key: str, candidates: list[dict[str, Any]], max_additions: int = 2) -> None:
            added = 0
            used_ids = {
                item.get("entity_id")
                for meal in meals
                for item in meal.get("items", [])
                if item.get("entity_id")
            }
            for candidate in candidates:
                current = totals()
                lower_bound = macro_lowers.get(nutrient_key, energy_lower)
                gap = lower_bound - current.get(nutrient_key, 0.0)
                if gap <= 0 or added >= max_additions:
                    return
                energy_room = max(energy_upper - current["energy_kcal"], 0.0)
                if energy_room <= 20:
                    return
                entity_id = candidate.get("entity_id")
                if not entity_id or entity_id in used_ids:
                    continue
                if self._candidate_realism_profile(
                    candidate,
                    goal,
                    dietary_preference=profile.get("dietary_preference"),
                )["hard_block"]:
                    continue
                nutrient_per_g = safe_float(candidate.get(nutrient_key), 0.0) / 100.0
                energy_per_g = safe_float(candidate.get("energy_kcal"), 0.0) / 100.0
                if nutrient_per_g <= 0 or energy_per_g <= 0:
                    continue
                meal = self._meal_with_macro_room(meals)
                if meal is None:
                    return
                cap = macro_portion_cap(candidate, meal.get("meal_name", ""))
                grams = min(cap, max(30.0, gap / max(nutrient_per_g, 0.01)), energy_room / energy_per_g)
                if grams < 30:
                    continue
                meal.setdefault("items", []).append(
                    {
                        "entity_id": entity_id,
                        "food_name": candidate.get("name"),
                        "grams": int(round(grams)),
                        "reason": "Macro closure support to keep calories and macros inside tolerance.",
                    }
                )
                used_ids.add(entity_id)
                added += 1

        def protein_count(meal: dict[str, Any]) -> int:
            return sum(
                1
                for item in meal.get("items", [])
                if (
                    candidate := candidate_lookup.get(item.get("entity_id"))
                )
                and self._candidate_is_main_meal_protein_anchor(
                    candidate,
                    goal,
                    profile.get("dietary_preference"),
                )
            )

        def reduce_excess_protein(soft: bool = False) -> None:
            tolerance_multiplier = 0.5 if soft else 1.0
            protein_upper = safe_float(targets.get("protein_g"), 0.0) * (
                1.0 + macro_tolerance * tolerance_multiplier
            )
            if protein_upper <= 0:
                return
            for _ in range(8):
                current = totals()
                if current["protein_g"] <= protein_upper or current["energy_kcal"] <= energy_lower:
                    return
                removable: list[tuple[float, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
                for meal in meals:
                    meal_items = meal.get("items", [])
                    meal_protein_count = protein_count(meal)
                    for item in meal_items:
                        candidate = candidate_lookup.get(item.get("entity_id"))
                        if candidate is None or self._candidate_role(candidate, goal) != "protein":
                            continue
                        if self._is_main_meal_name(meal.get("meal_name", "")) and meal_protein_count <= 1:
                            continue
                        item_energy = safe_float(candidate.get("energy_kcal"), 0.0) * item_grams(item) / 100.0
                        if current["energy_kcal"] - item_energy < energy_lower:
                            continue
                        protein = safe_float(candidate.get("protein_g"), 0.0) * item_grams(item) / 100.0
                        snack_bonus = 8.0 if not self._is_main_meal_name(meal.get("meal_name", "")) else 0.0
                        duplicate_bonus = max(meal_protein_count - 1, 0) * 3.0
                        removable.append((protein + snack_bonus + duplicate_bonus, meal, item, candidate))
                if not removable:
                    return
                _score, meal, item, _candidate = max(removable, key=lambda entry: entry[0])
                meal.get("items", []).remove(item)

        def reduce_excess_carbs_for_fat_rebalance(soft: bool = False) -> None:
            tolerance_multiplier = 0.5 if soft else 1.0
            carb_upper = safe_float(targets.get("carbs_g"), 0.0) * (
                1.0 + macro_tolerance * tolerance_multiplier
            )
            if carb_upper <= 0:
                return
            for _ in range(8):
                current = totals()
                carb_excess = current["carbs_g"] - carb_upper
                if carb_excess <= 0:
                    return
                removable: list[tuple[float, dict[str, Any], dict[str, Any], dict[str, Any], int]] = []
                for meal in meals:
                    is_main_meal = self._is_main_meal_name(meal.get("meal_name", ""))
                    for item in meal.get("items", []):
                        candidate = candidate_lookup.get(item.get("entity_id"))
                        if candidate is None:
                            continue
                        role = self._candidate_role(candidate, goal)
                        if role not in {"carb", "balanced"}:
                            continue
                        if self._is_healthy_fat_support(candidate, goal):
                            continue
                        current_grams = item_grams(item)
                        minimum_grams = 90 if is_main_meal and role == "carb" else 60
                        reducible_grams = max(current_grams - minimum_grams, 0)
                        if reducible_grams <= 0:
                            continue
                        carb_value = safe_float(candidate.get("carbs_g"), 0.0) * current_grams / 100.0
                        fat_value = safe_float(candidate.get("fat_g"), 0.0) * current_grams / 100.0
                        if carb_value <= max(fat_value * 2.0, 12.0):
                            continue
                        duplicate_bonus = sum(
                            1
                            for other_meal in meals
                            for other_item in other_meal.get("items", [])
                            if other_item is not item and other_item.get("entity_id") == item.get("entity_id")
                        ) * 4.0
                        removable.append((carb_value + duplicate_bonus, meal, item, candidate, reducible_grams))
                if not removable:
                    return
                _score, _meal, item, candidate, reducible_grams = max(removable, key=lambda entry: entry[0])
                current_grams = item_grams(item)
                carb_per_g = safe_float(candidate.get("carbs_g"), 0.0) / 100.0
                energy_per_g = safe_float(candidate.get("energy_kcal"), 0.0) / 100.0
                max_energy_reduction = max(current["energy_kcal"] - energy_lower, 0.0) / max(energy_per_g, 0.01)
                desired_delta = carb_excess / max(carb_per_g, 0.01)
                minimum_delta = 1.0 if carb_excess <= 8.0 else (8.0 if soft else 15.0)
                grams_delta = min(reducible_grams, max_energy_reduction, max(minimum_delta, desired_delta))
                if grams_delta < minimum_delta:
                    return
                set_item_grams(item, current_grams - grams_delta)

        healthy_fats = sorted(
            self._healthy_fat_candidates(candidate_pool, goal),
            key=lambda item: safe_float(item.get("fat_g"), 0.0),
            reverse=True,
        )
        carbs = sorted(
            [
                item
                for item in candidate_pool
                if self._candidate_role(item, goal) == "carb"
                and not self._candidate_realism_profile(item, goal)["hard_block"]
            ],
            key=lambda item: safe_float(item.get("carbs_g"), 0.0),
            reverse=True,
        )

        reduce_excess_protein()
        reduce_excess_carbs_for_fat_rebalance()
        increase_existing_for("fat_g", {"fat", "balanced", "produce"})
        add_support_for("fat_g", healthy_fats)
        reduce_excess_carbs_for_fat_rebalance()
        increase_existing_for("carbs_g", {"carb", "balanced"})
        add_support_for("carbs_g", carbs)
        increase_existing_for("energy_kcal", {"carb", "fat", "balanced", "produce"})
        reduce_excess_carbs_for_fat_rebalance()
        increase_existing_for("fat_g", {"fat", "balanced", "produce"})
        reduce_excess_carbs_for_fat_rebalance()
        reduce_excess_protein()
        soft_macro_target_ratio = max(0.0, 1.0 - macro_tolerance * 0.5)
        reduce_excess_carbs_for_fat_rebalance(soft=True)
        reduce_excess_protein(soft=True)
        increase_existing_for(
            "fat_g",
            {"fat", "balanced", "produce"},
            max_rounds=2,
            target_ratio=soft_macro_target_ratio,
        )
        reduce_excess_carbs_for_fat_rebalance(soft=True)
        return meals

    def _meal_with_macro_room(self, meals: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not meals:
            return None
        main_meals = [meal for meal in meals if self._is_main_meal_name(meal.get("meal_name", ""))]
        candidates = main_meals or meals
        candidates = [meal for meal in candidates if len(meal.get("items", [])) < 5] or candidates
        return min(candidates, key=lambda meal: len(meal.get("items", [])))
