from __future__ import annotations

import json
from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import safe_float
from app.services.nutrition_service import NutritionService

from .constants import GOAL_POOL_RULES


class WorkflowPlanningBuildersMixin:
    def _build_rule_based_attempt(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        candidates: list[dict[str, Any]],
        intent: Optional[NutritionIntent] = None,
    ) -> dict[str, Any]:
        selected_candidates = self._select_rule_based_candidates(profile, request, targets, candidates, intent)
        rule_based_attempts = []
        for strategy_name, plan_builder in [
            ("rule_based_mealwise", self._build_rule_based_plan_json),
            ("rule_based_daily", self._build_daily_rule_based_plan_json),
        ]:
            plan_json = plan_builder(profile, request, targets, selected_candidates, intent)
            resolved_plan = self._resolve_plan(plan_json, selected_candidates, allow_global_lookup=True)
            validation = self._validate_plan(
                resolved_plan,
                profile,
                request,
                targets,
                intent,
                attempt=request.max_revision_rounds + 1,
            )
            rule_based_attempts.append(
                {
                    "attempt": request.max_revision_rounds + 1,
                    "strategy": strategy_name,
                    "raw_text": json.dumps(plan_json, ensure_ascii=False),
                    "plan_json": plan_json,
                    "resolved_plan": resolved_plan,
                    "validation": validation,
                    "grounded_foods": self._grounded_foods_from_resolved_plan(resolved_plan),
                }
            )

        best_attempt = min(rule_based_attempts, key=self._attempt_sort_key)
        best_attempt["strategy"] = "rule_based_fallback"
        return best_attempt

    def _build_rule_based_plan_json(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        selected_candidates: list[dict[str, Any]],
        intent: Optional[NutritionIntent] = None,
    ) -> dict[str, Any]:
        goal = self._resolve_goal_family(profile, intent)
        balanced_meal_required = self._requires_balanced_health_bias(
            request,
            intent,
            self._resolve_retrieval_strategy(profile, intent),
        )
        meals = []
        for meal_index, template in enumerate(targets["meal_targets"]):
            subset = self._build_meal_candidate_subset(meal_index, goal, selected_candidates, request, intent)
            subset_lookup = {item.get("entity_id"): item for item in subset if item.get("entity_id")}
            optimization_input = [
                {
                    "entity_id": item["entity_id"],
                    "name": item["name"],
                    "calories": item["energy_kcal"],
                    "protein": item["protein_g"],
                    "carbs": item["carbs_g"],
                    "fat": item["fat_g"],
                }
                for item in subset
            ]
            optimized_items = NutritionService.optimize_meal(
                optimization_input,
                {
                    "calories": template["calories"],
                    "protein": template["protein_g"],
                    "carbs": template["carbs_g"],
                    "fat": template["fat_g"],
                },
                max_grams=300.0 if self._is_plant_based_diet(profile.get("dietary_preference")) else 400.0,
            )

            if not optimized_items:
                optimized_items = [
                    {
                        "entity_id": item["entity_id"],
                        "name": item["name"],
                        "calculated_grams": 120 if self._candidate_role(item, goal) != "produce" else 80,
                    }
                    for item in subset[:3]
                ]

            meal_items = [
                {
                    "entity_id": item.get("entity_id"),
                    "food_name": item.get("name"),
                    "grams": max(
                        30,
                        min(
                            int(item.get("calculated_grams", 120)),
                            self._portion_cap_for_candidate(
                                subset_lookup.get(item.get("entity_id"), {}),
                                goal,
                                template["meal_name"],
                            )
                            if subset_lookup.get(item.get("entity_id"))
                            else 400,
                        ),
                    ),
                    "reason": f"Nhóm món nền theo luật cho mục tiêu {goal} ở {template['meal_name'].lower()}",
                }
                for item in optimized_items[:4]
            ]
            meal_items = self._enforce_meal_realism_blueprint(
                template["meal_name"],
                meal_items,
                subset,
                goal,
                balanced_meal_required=balanced_meal_required,
            )
            meals.append(
                {
                    "meal_name": template["meal_name"],
                    "explanation": (
                        f"{template['meal_name']} sử dụng các món nền phù hợp mục tiêu từ tập candidate truy hồi "
                        f"để bám sát mục tiêu calo và macro cho {goal}, đồng thời tôn trọng ý định người dùng đã được phân tích."
                    ),
                    "items": meal_items,
                }
            )

        return {
            "summary": "Thực đơn theo luật được tạo từ các món nền phù hợp mục tiêu và bước tối ưu macro.",
            "reasoning": [
                "Tính TDEE và mục tiêu macro theo cơ chế xác định.",
                "Ưu tiên các món nền phù hợp với mục tiêu, ràng buộc và sở thích đã phân tích từ người dùng.",
                "Phân bổ gram cho từng bữa bằng bộ tối ưu macro để giữ calo và macro sát mục tiêu.",
            ],
            "meals": self._repair_meal_plan_macro_balance(
                goal=goal,
                meals=meals,
                candidate_pool=selected_candidates,
                targets=targets,
                profile=profile,
                request=request,
            ),
        }

    def _build_daily_rule_based_plan_json(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        selected_candidates: list[dict[str, Any]],
        intent: Optional[NutritionIntent] = None,
    ) -> dict[str, Any]:
        goal = self._resolve_goal_family(profile, intent)
        balanced_meal_required = self._requires_balanced_health_bias(
            request,
            intent,
            self._resolve_retrieval_strategy(profile, intent),
        )
        optimization_candidates = self._build_daily_optimization_subset(
            goal,
            selected_candidates,
            request,
            intent,
        )
        optimization_lookup = {
            item.get("entity_id"): item
            for item in optimization_candidates
            if item.get("entity_id")
        }
        optimization_input = [
            {
                "entity_id": item["entity_id"],
                "name": item["name"],
                "calories": item["energy_kcal"],
                "protein": item["protein_g"],
                "carbs": item["carbs_g"],
                "fat": item["fat_g"],
            }
            for item in optimization_candidates
        ]
        optimized_pool = NutritionService.optimize_meal(
            optimization_input,
            {
                "calories": targets["daily_calories"],
                "protein": targets["protein_g"],
                "carbs": targets["carbs_g"],
                "fat": targets["fat_g"],
            },
            max_grams=300.0 if self._is_plant_based_diet(profile.get("dietary_preference")) else 400.0,
        )
        optimized_pool = sorted(
            optimized_pool,
            key=lambda item: safe_float(item.get("calculated_calories"), 0.0),
            reverse=True,
        )
        optimized_pool = self._rebalance_daily_optimized_pool(
            goal,
            optimization_candidates,
            optimized_pool,
            targets,
        )

        meal_states = [
            {
                "meal_name": template["meal_name"],
                "explanation": "Kết quả tối ưu cả ngày được phân bổ vào từng bữa dựa trên lượng calo còn lại.",
                "items": [],
                "remaining_calories": template["calories"],
            }
            for template in targets["meal_targets"]
        ]

        for index, item in enumerate(optimized_pool):
            if index < len(meal_states):
                target_meal = meal_states[index]
            else:
                target_meal = max(meal_states, key=lambda meal: meal["remaining_calories"])
            mapped_candidate = optimization_lookup.get(item.get("entity_id"))
            target_meal["items"].append(
                {
                    "entity_id": item.get("entity_id"),
                    "food_name": item.get("name"),
                    "grams": max(
                        30,
                        min(
                            int(item.get("calculated_grams", 120)),
                            self._portion_cap_for_candidate(
                                mapped_candidate,
                                goal,
                                target_meal["meal_name"],
                            )
                            if mapped_candidate
                            else 400,
                        ),
                    ),
                    "reason": "Món được bổ sung từ bước tối ưu macro theo ngày.",
                }
            )
            target_meal["remaining_calories"] -= safe_float(item.get("calculated_calories"), 0.0)

        if any(not meal["items"] for meal in meal_states):
            fallback_seed = selected_candidates[: max(request.meal_count, 4)]
            for meal in meal_states:
                if meal["items"]:
                    continue
                seed = fallback_seed[len(meal["meal_name"]) % max(len(fallback_seed), 1)]
                meal["items"].append(
                    {
                        "entity_id": seed.get("entity_id"),
                        "food_name": seed.get("name"),
                        "grams": 120,
                        "reason": "Món hạt giống dự phòng để giữ đủ số bữa.",
                    }
                )

        for meal in meal_states:
            meal["items"] = self._enforce_meal_realism_blueprint(
                meal["meal_name"],
                meal["items"],
                optimization_candidates,
                goal,
                balanced_meal_required=balanced_meal_required,
            )

        return {
            "summary": "Phương án tối ưu theo ngày bằng luật đã được phân bổ lại vào các bữa ăn.",
            "reasoning": [
                "Tối ưu toàn bộ ngày theo mục tiêu calo và macro.",
                "Phân bổ thực phẩm đã tối ưu vào các bữa dựa trên phần calo còn lại.",
                "Giữ đúng số bữa ngay cả khi nhánh LLM không hoạt động.",
            ],
            "meals": [
                {
                    "meal_name": meal["meal_name"],
                    "explanation": meal["explanation"],
                    "items": meal["items"],
                }
                for meal in self._repair_meal_plan_macro_balance(
                    goal=goal,
                    meals=meal_states,
                    candidate_pool=optimization_candidates,
                    targets=targets,
                    profile=profile,
                    request=request,
                )
            ],
        }

    def _pick_best_attempt(self, attempts: list[dict[str, Any]]) -> dict[str, Any]:
        return min(attempts, key=self._attempt_sort_key)
