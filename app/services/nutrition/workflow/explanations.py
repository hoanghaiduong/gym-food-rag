from __future__ import annotations

import json
import textwrap
from copy import deepcopy
from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize

from .strings_vi import (
    DEFAULT_ITEM_REASON,
    build_default_meal_explanation,
    build_default_reasoning,
    build_default_summary,
    goal_context_label_vi,
)


class WorkflowExplanationsMixin:
    def _attach_plan_explanations(
        self,
        *,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        resolved_plan: dict[str, Any],
        validation: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> dict[str, Any]:
        default_summary = self._build_default_summary(profile, validation)
        default_reasoning = self._build_default_reasoning(profile, validation)
        default_meal_explanations = self._build_default_meal_explanations(resolved_plan, profile)

        enriched_plan = deepcopy(resolved_plan)
        enriched_plan["summary"] = default_summary
        enriched_plan["reasoning"] = default_reasoning
        for meal in enriched_plan.get("meals", []):
            meal["explanation"] = default_meal_explanations.get(meal["meal_name"], "")
            for item in meal.get("items", []):
                item["reason"] = item.get("reason") or DEFAULT_ITEM_REASON

        # LLM Refinement Layer (NEW per updated architecture): Uses Gemini-preferred LLM for UX only.
        # Strict prompt ensures no hallucination on macros/numbers. Deterministic core is preserved.
        try:
            prompt = self._build_explanation_prompt(
                profile,
                request,
                targets,
                enriched_plan,
                validation,
                intent,
            )
            raw_text = self.llm.generate_text(prompt, temperature=0.0)  # Factual, low creativity for explanations
            explanation_json = self.llm.parse_json(raw_text)
            return self._merge_explanation_json(enriched_plan, explanation_json)
        except Exception:
            return enriched_plan

    def _build_explanation_prompt(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        resolved_plan: dict[str, Any],
        validation: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> str:
        compact_meals = []
        for meal in resolved_plan.get("meals", []):
            compact_meals.append(
                {
                    "meal_name": meal.get("meal_name"),
                    "totals": meal.get("totals"),
                    "items": [
                        {
                            "food_name": item.get("food_name"),
                            "grams": item.get("grams"),
                            "energy_kcal": item.get("energy_kcal"),
                            "protein_g": item.get("protein_g"),
                            "carbs_g": item.get("carbs_g"),
                            "fat_g": item.get("fat_g"),
                        }
                        for item in meal.get("items", [])
                    ],
                }
            )

        # Improved prompt: balanced length + richer output guidance for better UX explanations
        # Strict guardrails preserved. Encourages motivational Vietnamese content with gym tips.
        prompt_template = f"""Bạn là HLV dinh dưỡng gym. Nhiệm vụ DUY NHẤT: Thêm giải thích UX tự nhiên, khích lệ bằng tiếng Việt (không thay đổi bất kỳ số liệu nào từ kế hoạch deterministic).

**TUÂN THỦ NGHIÊM (KHÔNG VI PHẠM)**:
- KHÔNG thay đổi grams, calo, macro, TDEE, danh sách món ăn hay totals.
- KHÔNG gợi ý thay đổi khẩu phần, món ăn hoặc recalculate.
- CHỈ cung cấp lý do chọn món, cách chuẩn bị/ăn, tips gym (compound, recovery, timing), synergy với tập luyện.

Profile: {json.dumps({k: profile.get(k) for k in ['age','gender','weight','height','activity_level','dietary_preference','target_goal']}, ensure_ascii=False, separators=(',', ':'))}
Mục tiêu: {json.dumps(targets, ensure_ascii=False, separators=(',', ':'))}
Kế hoạch: {json.dumps(compact_meals, ensure_ascii=False, separators=(',', ':'))}

Trả về **CHỈ JSON** (no markdown, no extra text):
{{
  "summary": "Tóm tắt ngắn gọn, động lực về kế hoạch và cách nó hỗ trợ mục tiêu gym",
  "reasoning": ["lý do chọn món chính", "phù hợp với TDEE/macro", "lời khuyên tập luyện cụ thể"],
  "meal_explanations": [
    {{
      "meal_name": "Bữa sáng",
      "explanation": "Giải thích chi tiết cách ăn, lợi ích dinh dưỡng, tips chuẩn bị nhanh, cách kết hợp với buổi tập (ví dụ: ăn trước/sau tập bao lâu), động lực duy trì",
      "item_reasons": [
        {{"food_name": "tên món chính xác", "reason": "lý do dinh dưỡng + hương vị + dễ ăn + synergy gym"}}
      ]
    }}
  ]
}}
"""
        return textwrap.dedent(prompt_template).strip()

    def _merge_explanation_json(
        self,
        resolved_plan: dict[str, Any],
        explanation_json: dict[str, Any],
    ) -> dict[str, Any]:
        merged = deepcopy(resolved_plan)
        if isinstance(explanation_json.get("summary"), str) and explanation_json.get("summary"):
            merged["summary"] = explanation_json["summary"]
        if isinstance(explanation_json.get("reasoning"), list):
            merged["reasoning"] = [
                str(item) for item in explanation_json["reasoning"] if isinstance(item, str)
            ] or merged.get("reasoning", [])

        explanation_by_meal = {}
        for meal_entry in explanation_json.get("meal_explanations", []) if isinstance(explanation_json.get("meal_explanations"), list) else []:
            meal_name = meal_entry.get("meal_name")
            if meal_name:
                explanation_by_meal[str(meal_name)] = meal_entry

        for meal in merged.get("meals", []):
            meal_payload = explanation_by_meal.get(meal.get("meal_name"), {})
            if isinstance(meal_payload.get("explanation"), str) and meal_payload.get("explanation"):
                meal["explanation"] = meal_payload["explanation"]
            item_reason_map = {}
            for item_payload in meal_payload.get("item_reasons", []) if isinstance(meal_payload.get("item_reasons"), list) else []:
                food_name = item_payload.get("food_name")
                reason = item_payload.get("reason")
                if food_name and isinstance(reason, str) and reason:
                    item_reason_map[ascii_normalize(food_name)] = reason
            for item in meal.get("items", []):
                normalized_name = ascii_normalize(item.get("food_name"))
                if normalized_name in item_reason_map:
                    item["reason"] = item_reason_map[normalized_name]
        return merged

    def _build_default_summary(self, profile: dict[str, Any], validation: dict[str, Any]) -> str:
        goal_label = goal_context_label_vi(
            profile.get("goal_raw_semantic"),
            self._resolve_goal_family(profile),
        )
        return build_default_summary(goal_label, validation.get("totals") or {})

    def _build_default_reasoning(self, profile: dict[str, Any], validation: dict[str, Any]) -> list[str]:
        goal_label = goal_context_label_vi(
            profile.get("goal_raw_semantic"),
            self._resolve_goal_family(profile),
        )
        return build_default_reasoning(goal_label, validation.get("totals") or {})

    def _build_default_meal_explanations(
        self,
        resolved_plan: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, str]:
        goal_label = goal_context_label_vi(
            profile.get("goal_raw_semantic"),
            self._resolve_goal_family(profile),
        )
        meal_explanations: dict[str, str] = {}
        for meal in resolved_plan.get("meals", []):
            meal_name = meal.get("meal_name", "Meal")
            top_items = ", ".join(
                item.get("food_name") for item in meal.get("items", [])[:3] if item.get("food_name")
            )
            meal_explanations[meal_name] = build_default_meal_explanation(
                meal_name,
                goal_label,
                meal.get("totals") or {},
                top_items,
            )
        return meal_explanations
