from __future__ import annotations

import json
from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import safe_float
from app.services.nutrition_service import NutritionService

from .constants import GOAL_POOL_RULES


class WorkflowPlanningRebalanceMixin:
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
        candidate_lookup = {
            candidate.get("entity_id"): candidate
            for candidate in candidate_pool
            if candidate.get("entity_id")
        }
        if not candidate_lookup:
            return meals

        meal_target_lookup = {
            template["meal_name"]: template
            for template in targets.get("meal_targets", [])
        }

        def _item_candidate(item: dict[str, Any]) -> Optional[dict[str, Any]]:
            return candidate_lookup.get(item.get("entity_id"))

        def _item_grams(item: dict[str, Any]) -> int:
            return max(int(round(safe_float(item.get("grams"), 0.0))), 0)

        def _item_macro(candidate: dict[str, Any], grams: float, key: str) -> float:
            return safe_float(candidate.get(key), 0.0) * grams / 100.0

        def _totals() -> dict[str, float]:
            totals = {"energy_kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
            for meal in meals:
                for item in meal.get("items", []):
                    candidate = _item_candidate(item)
                    if candidate is None:
                        continue
                    grams = _item_grams(item)
                    for key in totals:
                        totals[key] += _item_macro(candidate, grams, key)
            return totals

        def _meal_energy(meal: dict[str, Any]) -> float:
            total = 0.0
            for item in meal.get("items", []):
                candidate = _item_candidate(item)
                if candidate is not None:
                    total += _item_macro(candidate, _item_grams(item), "energy_kcal")
            return total

        def _role_counts() -> dict[str, int]:
            counts = {"protein": 0, "carb": 0, "produce": 0, "balanced": 0, "fat": 0}
            for meal in meals:
                for item in meal.get("items", []):
                    candidate = _item_candidate(item)
                    if candidate is None:
                        continue
                    counts[self._candidate_role(candidate, goal)] += 1
            return counts

        def _meal_roles(meal: dict[str, Any]) -> list[str]:
            roles: list[str] = []
            for item in meal.get("items", []):
                candidate = _item_candidate(item)
                if candidate is not None:
                    roles.append(self._candidate_role(candidate, goal))
            return roles

        # Phase 4 + edge cases: Soft diversity + discouraged_ratio check. If >0.35, trigger light repair (relax 1 item). Practical 3-5% tolerance.
        def _discouraged_ratio() -> float:
            total = sum(1 for m in meals for i in m.get("items", []))
            if total == 0: return 0.0
            discouraged = sum(1 for m in meals for i in m.get("items", []) if _item_candidate(i) and self._candidate_realism_profile(_item_candidate(i), goal).get("discouraged_reasons"))
            ratio = discouraged / total
            if ratio > 0.35:
                # Soft fallback: repair one high-discouraged item
                for meal in meals:
                    for item in meal.get("items", []):
                        cand = _item_candidate(item)
                        if cand and self._candidate_realism_profile(cand, goal).get("discouraged_reasons"):
                            item["grams"] = max(30, int(item.get("grams", 100)) * 0.7)  # reduce portion slightly
                            break
            return ratio

        def _portion_room(item: dict[str, Any], candidate: dict[str, Any], meal_name: str) -> int:
            cap = self._portion_cap_for_candidate(candidate, goal, meal_name)
            return max(cap - _item_grams(item), 0)

        def _set_item_grams(item: dict[str, Any], grams: int) -> None:
            item["grams"] = max(30, int(round(grams)))

        def _target_for_key(key: str) -> float:
            if key == "energy_kcal":
                return safe_float(targets.get("daily_calories"), 0.0)
            return safe_float(targets.get(key), 0.0)

        def _choose_meal_for_addition(prefer_main: bool = True) -> Optional[dict[str, Any]]:
            possible = [
                meal
                for meal in meals
                if len(meal.get("items", [])) < (5 if self._is_main_meal_name(meal.get("meal_name", "")) else 4)
            ]
            if prefer_main:
                main_possible = [
                    meal for meal in possible if self._is_main_meal_name(meal.get("meal_name", ""))
                ]
                if main_possible:
                    possible = main_possible
            if not possible:
                possible = meals
            if not possible:
                return None

            def _meal_gap(meal: dict[str, Any]) -> float:
                target = meal_target_lookup.get(meal.get("meal_name"), {})
                target_calories = safe_float(target.get("calories"), 0.0)
                return target_calories - _meal_energy(meal)

            return max(possible, key=_meal_gap)

        def _candidate_already_in_meal(meal: dict[str, Any], candidate: dict[str, Any]) -> bool:
            entity_id = candidate.get("entity_id")
            return bool(entity_id and any(item.get("entity_id") == entity_id for item in meal.get("items", [])))

        def _candidate_sort_key(candidate: dict[str, Any], nutrient_key: str) -> tuple[float, float, float]:
            protein = safe_float(candidate.get("protein_g"), 0.0)
            nutrient = safe_float(candidate.get(nutrient_key), 0.0)
            if nutrient_key == "fat_g":
                return (
                    nutrient / max(protein, 1.0),
                    nutrient,
                    safe_float(candidate.get("quality_score"), 0.0),
                )
            return (
                nutrient,
                self._goal_fit_score(candidate, goal, [], None),
                safe_float(candidate.get("quality_score"), 0.0),
            )

        def _add_candidate(
            candidate: dict[str, Any],
            *,
            nutrient_key: str,
            lower_ratio: float,
            reason: str,
            prefer_main: bool = True,
        ) -> bool:
            meal = _choose_meal_for_addition(prefer_main=prefer_main)
            if meal is None or _candidate_already_in_meal(meal, candidate):
                return False
            target = _target_for_key(nutrient_key) * lower_ratio
            current = _totals().get(nutrient_key, 0.0)
            gap = max(target - current, 0.0)
            per_100 = max(safe_float(candidate.get(nutrient_key), 0.0), 0.1)
            meal_name = meal.get("meal_name", "")
            cap = self._portion_cap_for_candidate(candidate, goal, meal_name)
            seed = self._seed_grams_for_candidate(candidate, goal, meal_name)
            grams = max(seed, int((gap / per_100 * 100.0) + 0.999))
            grams = max(30, min(grams, cap))
            meal.setdefault("items", []).append(
                {
                    "entity_id": candidate.get("entity_id"),
                    "food_name": candidate.get("name"),
                    "grams": grams,
                    "reason": reason,
                }
            )
            return True

        def _increase_existing(
            roles: set[str],
            *,
            nutrient_key: str,
            lower_ratio: float,
            max_rounds: int = 2,
        ) -> None:
            for _ in range(max_rounds):
                target = _target_for_key(nutrient_key) * lower_ratio
                current = _totals().get(nutrient_key, 0.0)
                gap = target - current
                if gap <= 0:
                    return
                plan_items: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
                for meal in meals:
                    for item in meal.get("items", []):
                        candidate = _item_candidate(item)
                        if candidate is None:
                            continue
                        if self._candidate_role(candidate, goal) not in roles:
                            continue
                        if _portion_room(item, candidate, meal.get("meal_name", "")) <= 0:
                            continue
                        plan_items.append((meal, item, candidate))
                if not plan_items:
                    return
                plan_items.sort(
                    key=lambda entry: _candidate_sort_key(entry[2], nutrient_key),
                    reverse=True,
                )
                changed = False
                for meal, item, candidate in plan_items:
                    target = _target_for_key(nutrient_key) * lower_ratio
                    current = _totals().get(nutrient_key, 0.0)
                    gap = target - current
                    if gap <= 0:
                        return
                    per_100 = safe_float(candidate.get(nutrient_key), 0.0)
                    if per_100 <= 0:
                        continue
                    room = _portion_room(item, candidate, meal.get("meal_name", ""))
                    if room <= 0:
                        continue
                    delta = max(20, int((gap / per_100 * 100.0) + 0.999))
                    delta = min(delta, room)
                    if delta <= 0:
                        continue
                    _set_item_grams(item, _item_grams(item) + delta)
                    changed = True
                if not changed:
                    return

        def _reduce_existing(
            roles: set[str],
            *,
            nutrient_key: str,
            upper_ratio: float,
            max_rounds: int = 2,
        ) -> None:
            for _ in range(max_rounds):
                target = _target_for_key(nutrient_key) * upper_ratio
                current = _totals().get(nutrient_key, 0.0)
                excess = current - target
                if excess <= 0:
                    return
                plan_items: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
                for meal in meals:
                    for item in meal.get("items", []):
                        candidate = _item_candidate(item)
                        if candidate is None:
                            continue
                        if self._candidate_role(candidate, goal) not in roles:
                            continue
                        if _item_grams(item) <= 30:
                            continue
                        plan_items.append((meal, item, candidate))
                if not plan_items:
                    return
                plan_items.sort(
                    key=lambda entry: safe_float(entry[2].get(nutrient_key), 0.0),
                    reverse=True,
                )
                changed = False
                for _meal, item, candidate in plan_items:
                    target = _target_for_key(nutrient_key) * upper_ratio
                    current = _totals().get(nutrient_key, 0.0)
                    excess = current - target
                    if excess <= 0:
                        return
                    per_100 = safe_float(candidate.get(nutrient_key), 0.0)
                    if per_100 <= 0:
                        continue
                    reducible = max(_item_grams(item) - 30, 0)
                    delta = max(10, int((excess / per_100 * 100.0) + 0.999))
                    delta = min(delta, reducible)
                    if delta <= 0:
                        continue
                    _set_item_grams(item, _item_grams(item) - delta)
                    changed = True
                if not changed:
                    return

        def _add_support_until(
            candidates: list[dict[str, Any]],
            *,
            nutrient_key: str,
            lower_ratio: float,
            reason: str,
            max_additions: int,
            prefer_main: bool = True,
        ) -> None:
            added = 0
            used_ids = {
                item.get("entity_id")
                for meal in meals
                for item in meal.get("items", [])
                if item.get("entity_id")
            }
            for candidate in candidates:
                if added >= max_additions:
                    return
                if _totals().get(nutrient_key, 0.0) >= _target_for_key(nutrient_key) * lower_ratio:
                    return
                entity_id = candidate.get("entity_id")
                if entity_id and entity_id in used_ids:
                    continue
                if self._candidate_realism_profile(candidate, goal)["hard_block"]:
                    continue
                if _add_candidate(
                    candidate,
                    nutrient_key=nutrient_key,
                    lower_ratio=lower_ratio,
                    reason=reason,
                    prefer_main=prefer_main,
                ):
                    added += 1
                    if entity_id:
                        used_ids.add(entity_id)

        def _trim_duplicate_lean_proteins() -> None:
            protein_target = safe_float(targets.get("protein_g"), 0.0)
            if protein_target <= 0:
                return
            while _totals()["protein_g"] > protein_target * 1.15:
                removable: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
                for meal in meals:
                    protein_items = [
                        (item, _item_candidate(item))
                        for item in meal.get("items", [])
                        if _item_candidate(item) is not None
                        and self._candidate_role(_item_candidate(item), goal) == "protein"
                    ]
                    allowed = 2 if self._is_main_meal_name(meal.get("meal_name", "")) else 1
                    if len(protein_items) <= allowed:
                        continue
                    for item, candidate in protein_items:
                        if candidate is None:
                            continue
                        fat = safe_float(candidate.get("fat_g"), 0.0)
                        protein = safe_float(candidate.get("protein_g"), 0.0)
                        removable.append((protein - fat, meal, item))
                if not removable:
                    return
                _, meal, item = max(removable, key=lambda entry: entry[0])
                meal["items"].remove(item)

        def _ensure_role_support() -> None:
            protein_candidates = [
                candidate
                for candidate in candidate_pool
                if self._candidate_role(candidate, goal) == "protein"
                and not self._candidate_realism_profile(candidate, goal, dietary_preference=profile.get("dietary_preference"))["hard_block"]
            ]
            protein_candidates.sort(key=lambda item: _candidate_sort_key(item, "protein_g"), reverse=True)
            for meal in meals:
                if not self._is_main_meal_name(meal.get("meal_name", "")):
                    continue
                if "protein" in _meal_roles(meal):
                    continue
                for candidate in protein_candidates:
                    if not _candidate_already_in_meal(meal, candidate):
                        meal["items"].insert(
                            0,
                            self._build_blueprint_item_from_candidate(
                                candidate,
                                goal,
                                meal.get("meal_name", ""),
                                "Bo sung nguon dam chinh de bua an khong bi toan mon phu.",
                            ),
                        )
                        break

            if goal == "gain_muscle":
                carb_candidates = [
                    candidate
                    for candidate in candidate_pool
                    if self._candidate_role(candidate, goal) == "carb"
                    and not self._candidate_realism_profile(candidate, goal)["hard_block"]
                ]
                carb_candidates.sort(key=lambda item: _candidate_sort_key(item, "carbs_g"), reverse=True)
                for meal in meals:
                    if not self._is_main_meal_name(meal.get("meal_name", "")):
                        continue
                    if "carb" in _meal_roles(meal):
                        continue
                    for candidate in carb_candidates:
                        if not _candidate_already_in_meal(meal, candidate):
                            meal["items"].append(
                                self._build_blueprint_item_from_candidate(
                                    candidate,
                                    goal,
                                    meal.get("meal_name", ""),
                                    "Bổ sung tinh bột nền để bữa tăng cân đủ năng lượng hơn.",
                                )
                            )
                            break
            elif goal == "lose_weight" and _role_counts()["produce"] < 1:
                produce_candidates = [
                    candidate
                    for candidate in candidate_pool
                    if self._candidate_role(candidate, goal) == "produce"
                    and not self._candidate_realism_profile(candidate, goal)["hard_block"]
                ]
                produce_candidates.sort(
                    key=lambda item: (
                        safe_float(item.get("quality_score"), 0.0),
                        -safe_float(item.get("energy_kcal"), 0.0),
                    ),
                    reverse=True,
                )
                if produce_candidates:
                    _add_candidate(
                        produce_candidates[0],
                        nutrient_key="energy_kcal",
                        lower_ratio=0.0,
                        reason="Bổ sung rau/quả thật để bữa giảm cân có chất xơ và không bị protein-only.",
                        prefer_main=True,
                    )

        _ensure_role_support()
        protein_candidates = sorted(
            [
                candidate
                for candidate in candidate_pool
                if self._candidate_role(candidate, goal) == "protein"
                and not self._candidate_realism_profile(candidate, goal, dietary_preference=profile.get("dietary_preference"))["hard_block"]
            ],
            key=lambda item: _candidate_sort_key(item, "protein_g"),
            reverse=True,
        )
        if _totals().get("protein_g", 0.0) < _target_for_key("protein_g") * 0.85:
            _increase_existing({"protein"}, nutrient_key="protein_g", lower_ratio=0.90, max_rounds=3)
            _add_support_until(
                protein_candidates,
                nutrient_key="protein_g",
                lower_ratio=0.90,
                reason="Bo sung dam neo bua chinh de protein gan muc tieu hon.",
                max_additions=3 if self._is_plant_based_diet(profile.get("dietary_preference")) else 2,
                prefer_main=True,
            )
        if goal == "lose_weight":
            _trim_duplicate_lean_proteins()

        healthy_fats = sorted(
            self._healthy_fat_candidates(candidate_pool, goal),
            key=lambda item: _candidate_sort_key(item, "fat_g"),
            reverse=True,
        )
        low_protein_fats = [
            candidate
            for candidate in healthy_fats
            if safe_float(candidate.get("protein_g"), 0.0)
            <= max(6.0, safe_float(candidate.get("fat_g"), 0.0) * 0.45)
        ]
        local_fat_hints = ["bo qua", "hat macca", "hat oc cho", "hat dieu"]
        for hint in local_fat_hints:
            for candidate in self.knowledge.search_local_candidates(
                hint,
                limit=3,
                dietary_preference=profile.get("dietary_preference"),
                allergy_tags=profile.get("allergy_tags"),
                excluded_foods=request.excluded_foods,
                entity_types=["food"],
            ):
                entity_id = candidate.get("entity_id")
                if not entity_id or entity_id in candidate_lookup:
                    continue
                if not self._is_healthy_fat_support(candidate, goal):
                    continue
                if safe_float(candidate.get("protein_g"), 0.0) > max(
                    6.0,
                    safe_float(candidate.get("fat_g"), 0.0) * 0.45,
                ):
                    continue
                candidate_pool.append(candidate)
                candidate_lookup[entity_id] = candidate
                low_protein_fats.append(candidate)
        low_protein_fats = sorted(
            low_protein_fats,
            key=lambda item: _candidate_sort_key(item, "fat_g"),
            reverse=True,
        )
        carbs = sorted(
            [
                candidate
                for candidate in candidate_pool
                if self._candidate_role(candidate, goal) == "carb"
                and not self._candidate_realism_profile(candidate, goal)["hard_block"]
            ],
            key=lambda item: _candidate_sort_key(item, "carbs_g"),
            reverse=True,
        )

        if goal == "gain_muscle":
            _increase_existing({"carb"}, nutrient_key="carbs_g", lower_ratio=0.90)
            _add_support_until(
                carbs,
                nutrient_key="carbs_g",
                lower_ratio=0.90,
                reason="Bổ sung tinh bột để kéo calo/carb về gần mục tiêu tăng cân.",
                max_additions=3,
                prefer_main=True,
            )
            _increase_existing({"fat", "balanced", "produce"}, nutrient_key="fat_g", lower_ratio=0.85)
            _add_support_until(
                low_protein_fats,
                nutrient_key="fat_g",
                lower_ratio=0.85,
                reason="Bổ sung chất béo tốt để tránh thực đơn tăng cân bị quá thiếu fat.",
                max_additions=3,
                prefer_main=False,
            )
            _increase_existing({"carb", "balanced", "fat", "produce"}, nutrient_key="energy_kcal", lower_ratio=0.92)
            _trim_duplicate_lean_proteins()
            _increase_existing({"carb", "balanced", "fat", "produce"}, nutrient_key="energy_kcal", lower_ratio=0.92)
            _increase_existing({"carb"}, nutrient_key="carbs_g", lower_ratio=0.88)
            _add_support_until(
                low_protein_fats,
                nutrient_key="fat_g",
                lower_ratio=0.85,
                reason="Bo sung fat it dam sau khi giam bot nguon protein trung lap.",
                max_additions=2,
                prefer_main=False,
            )
            _reduce_existing({"carb"}, nutrient_key="carbs_g", upper_ratio=1.14)
            _reduce_existing({"carb", "fat", "balanced", "produce"}, nutrient_key="energy_kcal", upper_ratio=1.08)
        elif goal == "lose_weight":
            _increase_existing({"fat", "balanced", "produce"}, nutrient_key="fat_g", lower_ratio=0.85)
            _add_support_until(
                low_protein_fats,
                nutrient_key="fat_g",
                lower_ratio=0.85,
                reason="Bổ sung chất béo tốt vừa phải để macro giảm cân không bị quá lệch.",
                max_additions=2,
                prefer_main=False,
            )
            _increase_existing({"carb", "produce", "balanced"}, nutrient_key="carbs_g", lower_ratio=0.90)
            _add_support_until(
                carbs,
                nutrient_key="carbs_g",
                lower_ratio=0.90,
                reason="Bổ sung tinh bột vừa phải để giữ calo giảm cân trong ngưỡng.",
                max_additions=2,
                prefer_main=True,
            )
            _trim_duplicate_lean_proteins()
            _increase_existing({"fat", "balanced", "produce"}, nutrient_key="fat_g", lower_ratio=0.85)
            _add_support_until(
                low_protein_fats,
                nutrient_key="fat_g",
                lower_ratio=0.85,
                reason="Bo sung fat it dam sau khi giam bot nguon protein trung lap.",
                max_additions=2,
                prefer_main=False,
            )
            _increase_existing({"carb", "produce", "balanced"}, nutrient_key="energy_kcal", lower_ratio=0.90)
            _reduce_existing({"carb"}, nutrient_key="carbs_g", upper_ratio=1.14)
            _reduce_existing({"carb", "fat", "balanced", "produce"}, nutrient_key="energy_kcal", upper_ratio=1.08)
        else:
            _increase_existing({"carb", "balanced"}, nutrient_key="carbs_g", lower_ratio=0.88)
            _increase_existing({"fat", "balanced", "produce"}, nutrient_key="fat_g", lower_ratio=0.85)
            _add_support_until(
                healthy_fats,
                nutrient_key="fat_g",
                lower_ratio=0.85,
                reason="Bổ sung chất béo tốt để bữa ăn cân bằng hơn.",
                max_additions=2,
                prefer_main=False,
            )

        if _totals().get("protein_g", 0.0) > _target_for_key("protein_g") * 1.15:
            _reduce_existing({"protein"}, nutrient_key="protein_g", upper_ratio=1.12, max_rounds=3)
            _increase_existing({"fat", "balanced", "carb"}, nutrient_key="fat_g", lower_ratio=0.85)
            _add_support_until(
                low_protein_fats,
                nutrient_key="fat_g",
                lower_ratio=0.85,
                reason="Bo sung fat it dam de can bang lai sau khi giam protein qua cao.",
                max_additions=2,
                prefer_main=False,
            )
        if _totals().get("energy_kcal", 0.0) < _target_for_key("energy_kcal") * 0.90:
            _increase_existing({"carb", "fat", "balanced"}, nutrient_key="energy_kcal", lower_ratio=0.92, max_rounds=2)
        if _totals().get("energy_kcal", 0.0) > _target_for_key("energy_kcal") * 1.08:
            _reduce_existing({"carb", "fat", "balanced", "produce"}, nutrient_key="energy_kcal", upper_ratio=1.06, max_rounds=2)

        return meals

    def _rebalance_daily_optimized_pool(
        self,
        goal: str,
        optimization_candidates: list[dict[str, Any]],
        optimized_pool: list[dict[str, Any]],
        targets: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if goal not in {"lose_weight", "maintain"} or not optimized_pool:
            return optimized_pool

        def _scale_item(item: dict[str, Any], target_grams: int) -> None:
            current_grams = max(int(item.get("calculated_grams", 0)), 1)
            target_grams = max(30, target_grams)
            if target_grams >= current_grams:
                return
            scale = target_grams / current_grams
            item["calculated_grams"] = target_grams
            item["calculated_calories"] = round(safe_float(item.get("calculated_calories"), 0.0) * scale, 1)
            item["calculated_protein"] = round(safe_float(item.get("calculated_protein"), 0.0) * scale, 1)
            item["calculated_carbs"] = round(safe_float(item.get("calculated_carbs"), 0.0) * scale, 1)
            item["calculated_fat"] = round(safe_float(item.get("calculated_fat"), 0.0) * scale, 1)

        current_protein = sum(safe_float(item.get("calculated_protein"), 0.0) for item in optimized_pool)
        current_fat = sum(safe_float(item.get("calculated_fat"), 0.0) for item in optimized_pool)
        protein_target = safe_float(targets.get("protein_g"), 0.0)
        fat_target = safe_float(targets.get("fat_g"), 0.0)

        protein_excess = current_protein - protein_target
        fat_gap = fat_target - current_fat
        if protein_excess <= 12 and fat_gap <= 6:
            return optimized_pool

        rebalanced = [dict(item) for item in optimized_pool]

        if goal == "lose_weight":
            for item in rebalanced:
                mapped_candidate = next(
                    (
                        candidate for candidate in optimization_candidates
                        if candidate.get("entity_id") == item.get("entity_id")
                    ),
                    None,
                )
                if mapped_candidate is None:
                    continue
                role = self._candidate_role(mapped_candidate, goal)
                realism = self._candidate_realism_profile(mapped_candidate, goal)
                current_grams = max(int(item.get("calculated_grams", 0)), 30)
                gram_cap = 220
                if role == "protein":
                    gram_cap = 180
                elif role in {"balanced", "fat"}:
                    gram_cap = 140
                elif role == "produce":
                    gram_cap = 180
                if any(reason in {"high_fat_protein_for_weight_loss", "very_high_fat"} for reason in realism["discouraged_reasons"]):
                    gram_cap = min(gram_cap, 140)
                if current_grams > gram_cap:
                    _scale_item(item, gram_cap)

        current_protein = sum(safe_float(item.get("calculated_protein"), 0.0) for item in rebalanced)
        protein_excess = current_protein - protein_target
        if protein_excess > 12:
            lean_proteins = sorted(
                [
                    item for item in rebalanced
                    if safe_float(item.get("calculated_protein"), 0.0) >= 18
                    and safe_float(item.get("calculated_fat"), 0.0) <= 8
                ],
                key=lambda item: safe_float(item.get("calculated_protein"), 0.0),
                reverse=True,
            )
            remaining_excess = protein_excess
            for item in lean_proteins:
                if remaining_excess <= 0:
                    break
                current_grams = max(int(item.get("calculated_grams", 0)), 30)
                reducible_grams = max(current_grams - 60, 0)
                if reducible_grams <= 0:
                    continue
                ratio = reducible_grams / max(current_grams, 1)
                protein_drop = safe_float(item.get("calculated_protein"), 0.0) * ratio
                grams_delta = min(reducible_grams, int(round(current_grams * 0.25)))
                if grams_delta <= 0:
                    continue
                scale = (current_grams - grams_delta) / max(current_grams, 1)
                item["calculated_grams"] = max(60, current_grams - grams_delta)
                item["calculated_calories"] = round(safe_float(item.get("calculated_calories"), 0.0) * scale, 1)
                item["calculated_protein"] = round(safe_float(item.get("calculated_protein"), 0.0) * scale, 1)
                item["calculated_carbs"] = round(safe_float(item.get("calculated_carbs"), 0.0) * scale, 1)
                item["calculated_fat"] = round(safe_float(item.get("calculated_fat"), 0.0) * scale, 1)
                remaining_excess -= protein_drop

        current_protein = sum(safe_float(item.get("calculated_protein"), 0.0) for item in rebalanced)
        current_fat = sum(safe_float(item.get("calculated_fat"), 0.0) for item in rebalanced)
        fat_gap = fat_target - current_fat
        if fat_gap > 4:
            healthy_fat_candidates = self._healthy_fat_candidates(optimization_candidates, goal)
            existing_ids = {item.get("entity_id") for item in rebalanced}
            additions = [item for item in healthy_fat_candidates if item.get("entity_id") not in existing_ids]
            if additions:
                support = additions[0]
                fat_per_100 = max(safe_float(support.get("fat_g"), 0.0), 0.1)
                grams = max(30, min(int(round(fat_gap / fat_per_100 * 100)), 120))
                factor = grams / 100.0
                rebalanced.append(
                    {
                        "entity_id": support.get("entity_id"),
                        "name": support.get("name"),
                        "calculated_grams": grams,
                        "calculated_calories": round(safe_float(support.get("energy_kcal"), 0.0) * factor, 1),
                        "calculated_protein": round(safe_float(support.get("protein_g"), 0.0) * factor, 1),
                        "calculated_carbs": round(safe_float(support.get("carbs_g"), 0.0) * factor, 1),
                        "calculated_fat": round(safe_float(support.get("fat_g"), 0.0) * factor, 1),
                    }
                )

        current_carbs = sum(safe_float(item.get("calculated_carbs"), 0.0) for item in rebalanced)
        current_calories = sum(safe_float(item.get("calculated_calories"), 0.0) for item in rebalanced)
        carb_gap = safe_float(targets.get("carbs_g"), 0.0) - current_carbs
        calorie_gap = safe_float(targets.get("daily_calories"), 0.0) - current_calories
        if goal == "lose_weight" and (carb_gap > 8 or calorie_gap > 80):
            existing_ids = {item.get("entity_id") for item in rebalanced}
            carb_support = [
                item
                for item in optimization_candidates
                if item.get("entity_id") not in existing_ids
                and self._candidate_role(item, goal) in {"carb", "produce", "balanced"}
                and not self._candidate_realism_profile(item, goal)["hard_block"]
            ]
            carb_support = sorted(
                carb_support,
                key=lambda item: (
                    self._goal_fit_score(item, goal, [], None),
                    safe_float(item.get("quality_score"), 0.0),
                ),
                reverse=True,
            )
            if carb_support:
                support = carb_support[0]
                carb_per_100 = max(safe_float(support.get("carbs_g"), 0.0), 0.1)
                grams = max(30, min(int(round(carb_gap / carb_per_100 * 100)), 160))
                factor = grams / 100.0
                rebalanced.append(
                    {
                        "entity_id": support.get("entity_id"),
                        "name": support.get("name"),
                        "calculated_grams": grams,
                        "calculated_calories": round(safe_float(support.get("energy_kcal"), 0.0) * factor, 1),
                        "calculated_protein": round(safe_float(support.get("protein_g"), 0.0) * factor, 1),
                        "calculated_carbs": round(safe_float(support.get("carbs_g"), 0.0) * factor, 1),
                        "calculated_fat": round(safe_float(support.get("fat_g"), 0.0) * factor, 1),
                    }
                )

        return sorted(
            [item for item in rebalanced if int(item.get("calculated_grams", 0)) >= 30],
            key=lambda item: safe_float(item.get("calculated_calories"), 0.0),
            reverse=True,
        )
