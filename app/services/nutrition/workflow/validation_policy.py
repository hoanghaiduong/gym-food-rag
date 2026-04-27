from __future__ import annotations

import re
from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize, safe_float
from app.services.nutrition.knowledge.diet_compatibility import matches_dietary_preference
from app.services.nutrition.knowledge.exclusion_matching import normalized_text_matches_exclusion
from app.services.nutrition_record_policy import ANIMAL_PROTEIN_PATTERNS, STARCH_STAPLE_PATTERNS


class WorkflowValidationPolicyMixin:
    def _validate_plan(
        self,
        resolved_plan: dict[str, Any],
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
        *,
        attempt: int = 0,
    ) -> dict[str, Any]:
        issues = []
        failed_checks = 0
        total_checks = 6
        meals = resolved_plan.get("meals", [])
        if len(meals) != request.meal_count:
            issues.append(
                {
                    "code": "meal_count_mismatch",
                    "severity": "error",
                    "message": f"Expected {request.meal_count} meals but received {len(meals)}.",
                    "details": {"expected": request.meal_count, "actual": len(meals)},
                }
            )
            failed_checks += 1

        unresolved_items = []
        gram_issues = []
        allergy_hits = []
        preference_hits = []
        realism_blocked = []
        realism_discouraged = []
        discouraged_energy_kcal = 0.0
        unsafe_output_hits = []
        unsafe_label_hits = []
        substituted_to_safe_variant_count = 0
        role_counts = {"protein": 0, "carb": 0, "produce": 0, "balanced": 0, "fat": 0}
        main_meal_role_issues = []
        goal = self._resolve_goal_family(profile)
        for meal in meals:
            meal_roles = []
            meal_has_protein_anchor = False
            meal_items = meal.get("items", [])
            for item in meal_items:
                if not item.get("resolved"):
                    unresolved_items.append(item.get("food_name"))
                if item.get("grams", 0) < 30 or item.get("grams", 0) > 400:
                    gram_issues.append({"food_name": item.get("food_name"), "grams": item.get("grams")})
                if item.get("final_output_allowed") is False:
                    unsafe_output_hits.append(
                        {
                            "food_name": item.get("food_name"),
                            "source_food_name": item.get("source_food_name"),
                            "unsafe_output_reason": item.get("unsafe_output_reason"),
                            "entity_id": item.get("entity_id"),
                        }
                    )
                if self._is_unsafe_output_label(item):
                    unsafe_label_hits.append(
                        {
                            "food_name": item.get("food_name"),
                            "entity_id": item.get("entity_id"),
                        }
                    )
                if item.get("substituted_to_safe_variant"):
                    substituted_to_safe_variant_count += 1
                if set(profile.get("allergy_tags") or []).intersection(set(item.get("allergen_tags") or [])):
                    allergy_hits.append(item.get("food_name"))
                if not self._matches_preference(
                    profile.get("dietary_preference"),
                    item.get("diet_tags") or [],
                    item,
                ):
                    preference_hits.append(item.get("food_name"))
                realism = self._candidate_realism_profile(
                    item,
                    goal,
                    dietary_preference=profile.get("dietary_preference"),
                )
                item_role = self._candidate_role(item, goal)
                role_counts[item_role] += 1
                meal_roles.append(item_role)
                if self._candidate_is_main_meal_protein_anchor(
                    item,
                    goal,
                    profile.get("dietary_preference"),
                ):
                    meal_has_protein_anchor = True
                if realism["hard_block"]:
                    realism_blocked.append(
                        {
                            "food_name": item.get("food_name"),
                            "source_food_name": item.get("source_food_name"),
                            "reasons": realism["hard_block_reasons"],
                        }
                    )
                elif realism["discouraged_reasons"]:
                    realism_discouraged.append(
                        {
                            "food_name": item.get("food_name"),
                            "reasons": realism["discouraged_reasons"],
                            "energy_kcal": item.get("energy_kcal"),
                        }
                    )
                    discouraged_energy_kcal += safe_float(item.get("energy_kcal"), 0.0)
            if self._is_main_meal_name(meal.get("meal_name")):
                if not meal_has_protein_anchor:
                    main_meal_role_issues.append(
                        {
                            "meal_name": meal.get("meal_name"),
                            "reason": "missing_protein_anchor",
                            "roles": meal_roles,
                        }
                    )
                if meal_items and len(meal_items) == 1 and all(role in {"produce", "fat", "balanced"} for role in meal_roles):
                    main_meal_role_issues.append(
                        {
                            "meal_name": meal.get("meal_name"),
                            "reason": "single_support_like_item",
                            "roles": meal_roles,
                        }
                    )

        if unresolved_items:
            issues.append(
                {
                    "code": "unresolved_foods",
                    "severity": "error",
                    "message": "Some generated foods could not be grounded to the canonical knowledge base.",
                    "details": {"foods": unresolved_items},
                }
            )
            failed_checks += 1
        total_checks += 1
        if unsafe_output_hits or unsafe_label_hits:
            issues.append(
                {
                    "code": "unsafe_food_output_present",
                    "severity": "error",
                    "message": "The plan contains foods or labels that are unsafe for final user-facing output.",
                    "details": {
                        "blocked_items": unsafe_output_hits,
                        "unsafe_labels": unsafe_label_hits,
                        "unsafe_raw_output_count": len(unsafe_output_hits),
                        "unsafe_label_count": len(unsafe_label_hits),
                    },
                }
            )
            failed_checks += 1
        if gram_issues:
            issues.append(
                {
                    "code": "grams_out_of_range",
                    "severity": "error",
                    "message": "Some selected items have grams outside the 30-400 range.",
                    "details": {"items": gram_issues},
                }
            )
            failed_checks += 1
        if profile.get("allergy_tags"):
            total_checks += 1
            if allergy_hits:
                issues.append(
                    {
                        "code": "allergy_violation",
                        "severity": "error",
                        "message": "The plan contains foods matching the user's allergy tags.",
                        "details": {"foods": allergy_hits, "allergy_tags": profile["allergy_tags"]},
                    }
                )
                failed_checks += 1
        if profile.get("dietary_preference") and profile.get("dietary_preference") != "omnivore":
            total_checks += 1
            dietary_override = profile.get("dietary_override", False)
            if preference_hits and not dietary_override:
                issues.append(
                    {
                        "code": "dietary_preference_violation",
                        "severity": "error",
                        "message": "The plan contains foods outside the requested dietary preference.",
                        "details": {
                            "foods": preference_hits,
                            "dietary_preference": profile["dietary_preference"],
                        },
                    }
                )
                failed_checks += 1

        normalized_exclusions = [ascii_normalize(item) for item in request.excluded_foods]
        if normalized_exclusions:
            total_checks += 1
            all_resolved_items = [item for meal in meals for item in meal.get("items", [])]
            violated_exclusions = [
                item.get("food_name")
                for item in all_resolved_items
                if any(
                    normalized_text_matches_exclusion(
                        ascii_normalize(
                            " ".join(
                                str(value)
                                for value in [
                                    item.get("food_name"),
                                    item.get("source_food_name"),
                                    item.get("safe_display_name"),
                                ]
                                if value
                            )
                        ),
                        exclusion,
                    )
                    for exclusion in normalized_exclusions
                )
            ]
            if violated_exclusions:
                issues.append(
                    {
                        "code": "excluded_food_present",
                        "severity": "error",
                        "message": "The plan includes foods that were explicitly excluded.",
                        "details": {"foods": violated_exclusions},
                    }
                )
                failed_checks += 1

        normalized_must_include = [ascii_normalize(item) for item in request.must_include]
        if normalized_must_include:
            total_checks += 1
            all_resolved_items = [item for meal in meals for item in meal.get("items", [])]
            missing_required = [
                item
                for item in normalized_must_include
                if not any(self._candidate_matches_hint(candidate, item) for candidate in all_resolved_items)
            ]
            if missing_required:
                issues.append(
                    {
                        "code": "must_include_missing",
                        "severity": "warning",
                        "message": "Some preferred foods were not included in the plan.",
                        "details": {"foods": missing_required},
                    }
                )

        total_checks += 1
        if realism_blocked:
            issues.append(
                {
                    "code": "meal_realism_blocked_items",
                    "severity": "error",
                    "message": "The plan contains foods that are not suitable as primary meal-planning items.",
                    "details": {"items": realism_blocked},
                }
            )
            failed_checks += 1

        total_checks += 1
        realism_role_error = self._validate_role_coverage(goal, role_counts)
        if main_meal_role_issues:
            issues.append(
                {
                    "code": "meal_realism_main_meal_anchor",
                    "severity": "error",
                    "message": "Each main meal must include at least one practical protein anchor and cannot be support-only.",
                    "details": {"meals": main_meal_role_issues},
                }
            )
            failed_checks += 1
        elif realism_role_error:
            issues.append(realism_role_error)
            failed_checks += 1
        elif realism_discouraged:
            total_energy = max(safe_float(resolved_plan.get("totals", {}).get("energy_kcal"), 0.0), 1.0)
            discouraged_share = discouraged_energy_kcal / total_energy
            is_plant_diet = self._is_plant_based_diet(profile.get("dietary_preference"))
            budget_level = (profile.get("budget_level") or "").lower()
            if is_plant_diet:
                effective_discouraged = [
                    item
                    for item in realism_discouraged
                    if not all(reason == "high_fat_protein_for_weight_loss" for reason in item.get("reasons", []))
                ]
                effective_energy = sum(safe_float(item.get("energy_kcal"), 0.0) for item in effective_discouraged)
                effective_share = effective_energy / total_energy
                discouraged_threshold = 0.45
                discouraged_count_threshold = max(request.meal_count, 4) + 2
            else:
                effective_discouraged = realism_discouraged
                effective_share = discouraged_share
                discouraged_threshold = 0.65 if "budget" in budget_level or "low" in budget_level else 0.35
                discouraged_count_threshold = max(request.meal_count, 4) + 3 if "budget" in budget_level or "low" in budget_level else max(request.meal_count, 4)
            if effective_share >= discouraged_threshold or len(effective_discouraged) >= discouraged_count_threshold:
                issues.append(
                    {
                        "code": "meal_realism_discouraged_dominant",
                        "severity": "error",
                        "message": "Too much of the plan's calories come from discouraged meal-planning items.",
                        "details": {
                            "items": realism_discouraged[:8],
                            "discouraged_energy_kcal": round(discouraged_energy_kcal, 1),
                            "discouraged_share_pct": round(discouraged_share * 100, 2),
                        },
                    }
                )
                failed_checks += 1
            else:
                issues.append(
                    {
                        "code": "meal_realism_discouraged_items",
                        "severity": "warning",
                        "message": "Thực đơn có một số món tuy đạt yêu cầu định lượng nhưng chưa thật sự phù hợp với bữa ăn thực tế.",
                        "details": {"items": realism_discouraged[:8]},
                    }
                )

        totals = resolved_plan.get("totals", {})
        dietary_preference = profile.get("dietary_preference")
        budget_level = profile.get("budget_level") or (getattr(intent, "budget_level", None) if intent else None)
        effective_calorie_tol, effective_macro_tol = self._diet_aware_tolerances(
            dietary_preference,
            request.calorie_tolerance_pct,
            request.macro_tolerance_pct,
            budget_level=budget_level,
        )
        calorie_error_pct = self._pct_error(totals.get("energy_kcal", 0.0), targets["daily_calories"])
        protein_error_pct = self._pct_error(totals.get("protein_g", 0.0), targets["protein_g"])
        carbs_error_pct = self._pct_error(totals.get("carbs_g", 0.0), targets["carbs_g"])
        fat_error_pct = self._pct_error(totals.get("fat_g", 0.0), targets["fat_g"])
        if calorie_error_pct > effective_calorie_tol:
            issues.append(
                {
                    "code": "calorie_target_miss",
                    "severity": "error",
                    "message": "Total calories are outside the allowed tolerance.",
                    "details": {
                        "actual": totals.get("energy_kcal", 0.0),
                        "target": targets["daily_calories"],
                        "error_pct": round(calorie_error_pct * 100, 2),
                    },
                }
            )
            failed_checks += 1
        for macro_key, error_pct in {
            "protein_g": protein_error_pct,
            "carbs_g": carbs_error_pct,
            "fat_g": fat_error_pct,
        }.items():
            if error_pct > effective_macro_tol:
                explanation = ""
                if macro_key == "protein_g" and profile.get("dietary_preference") in ["vegetarian", "vegan"]:
                    explanation = (
                        "Low protein due to vegetarian/vegan dietary constraint. Consider: "
                        "(1) Add more high-protein plant foods (tofu, beans, nuts), "
                        "(2) Adjust dietary preference to omnivore or pescatarian, "
                        "(3) Increase meal count"
                    )
                elif macro_key == "carbs_g":
                    explanation = (
                        "Carbohydrate target missed. Consider: "
                        "(1) Increase grain/starchy vegetable portions, "
                        "(2) Add more high-carb foods, "
                        "(3) Review meal count and distribution"
                    )
                elif macro_key == "fat_g":
                    explanation = "Fat target missed. Adjust oil, nuts, or fatty foods in meals accordingly."

                issue_detail = {
                    "actual": totals.get(macro_key, 0.0),
                    "target": targets[macro_key],
                    "error_pct": round(error_pct * 100, 2),
                }
                if explanation:
                    issue_detail["explanation"] = explanation

                issues.append(
                    {
                        "code": f"{macro_key}_target_miss",
                        "severity": "error",
                        "message": f"{macro_key} is outside the allowed tolerance.",
                        "details": issue_detail,
                    }
                )
                failed_checks += 1

        if self._is_plant_based_diet(profile.get("dietary_preference")):
            all_items = [item for meal in meals for item in meal.get("items", [])]
            if all_items and not self._has_sufficient_protein_density(all_items, min_density=6.0):
                issues.append(
                    {
                        "code": "insufficient_protein_density",
                        "severity": "warning",
                        "message": (
                            "No item in the plan has sufficient protein density (>=6g/100g). "
                            "Consider adding tofu, tempeh, legumes, or seitan for better protein coverage."
                        ),
                        "details": {
                            "suggestion": ["đậu phụ", "tempeh", "đậu lăng", "đậu đen", "seitan", "edamame"],
                        },
                    }
                )

        issue_codes = {str(issue.get("code") or "") for issue in issues if issue.get("severity") == "error"}
        return {
            "passed": not any(issue["severity"] == "error" for issue in issues),
            "attempt": attempt,
            "totals": {
                "energy_kcal": round(totals.get("energy_kcal", 0.0), 1),
                "protein_g": round(totals.get("protein_g", 0.0), 1),
                "carbs_g": round(totals.get("carbs_g", 0.0), 1),
                "fat_g": round(totals.get("fat_g", 0.0), 1),
            },
            "calorie_error_kcal": round(abs(totals.get("energy_kcal", 0.0) - targets["daily_calories"]), 1),
            "calorie_error_pct": round(calorie_error_pct * 100, 2),
            "macro_deviation_pct": round(((protein_error_pct + carbs_error_pct + fat_error_pct) / 3.0) * 100, 2),
            "macro_errors_pct": {
                "protein_g": round(protein_error_pct * 100, 2),
                "carbs_g": round(carbs_error_pct * 100, 2),
                "fat_g": round(fat_error_pct * 100, 2),
            },
            "macro_error": bool(
                {"calorie_target_miss", "protein_g_target_miss", "carbs_g_target_miss", "fat_g_target_miss"}
                & issue_codes
            ),
            "meal_realism_error": any(code.startswith("meal_realism_") for code in issue_codes),
            "unsafe_raw_output_count": len(unsafe_output_hits),
            "unsafe_label_count": len(unsafe_label_hits),
            "substituted_to_safe_variant_count": substituted_to_safe_variant_count,
            "safety_error": bool(
                {
                    "allergy_violation",
                    "dietary_preference_violation",
                    "excluded_food_present",
                    "unsafe_food_output_present",
                }
                & issue_codes
            ),
            "violation_rate": round(failed_checks / max(total_checks, 1), 3),
            "issues": issues,
        }

    def _grounded_foods_from_resolved_plan(self, resolved_plan: dict[str, Any]) -> list[dict[str, Any]]:
        grounded = {}
        for meal in resolved_plan.get("meals", []):
            for item in meal.get("items", []):
                if not item.get("resolved") or not item.get("entity_id"):
                    continue
                grounded[item["entity_id"]] = self.knowledge.resolve_food_reference(
                    entity_id=item["entity_id"],
                    food_name=item.get("food_name"),
                    candidate_map={},
                    allow_global_lookup=True,
                    allow_blocked_lookup=True,
                )
        return [item for item in grounded.values() if item]

    def _matches_preference(
        self,
        dietary_preference: Optional[str],
        diet_tags: list[str],
        item: Optional[dict[str, Any]] = None,
    ) -> bool:
        return matches_dietary_preference(dietary_preference, diet_tags, item)

    def _is_unsafe_output_label(self, item: dict[str, Any]) -> bool:
        normalized_name = ascii_normalize(item.get("food_name"))
        if not normalized_name:
            return False
        if item.get("consumption_state") == "direct_edible_raw":
            return False
        if not any(marker in f" {normalized_name}" for marker in [" raw", " fresh", " tuoi", " song"]):
            return False
        if self._normalized_name_matches_patterns(normalized_name, ANIMAL_PROTEIN_PATTERNS):
            return True
        if self._normalized_name_matches_patterns(normalized_name, STARCH_STAPLE_PATTERNS):
            return True
        return any(token in normalized_name for token in ["rau", "cu ", "cu,", "qua ", "qua,"])

    def _normalized_name_matches_patterns(self, normalized_name: str, patterns: list[str]) -> bool:
        tokens = set(re.sub(r"[^a-z0-9]+", " ", normalized_name).split())
        for pattern in patterns:
            normalized_pattern = ascii_normalize(pattern)
            if not normalized_pattern:
                continue
            if " " in normalized_pattern:
                if normalized_pattern in normalized_name:
                    return True
                continue
            if normalized_pattern in tokens:
                return True
        return False

    def _clean_food_display_name(self, name: str) -> str:
        """Clean food names without hiding raw inedible source items."""
        if not name or not isinstance(name, str):
            return name
        cleaned = name.strip()
        normalized_original = ascii_normalize(cleaned.lower())
        if "song" in set(re.sub(r"[^a-z0-9]+", " ", normalized_original).split()):
            return cleaned.strip(" ,")

        cleaned = cleaned.replace(", tươi", "").replace(",tươi", "").replace(" , tươi", "")
        return cleaned.strip(" ,") or name
