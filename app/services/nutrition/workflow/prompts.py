from __future__ import annotations

import json
from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent

from .strings_vi import RAW_FOOD_KEYWORD


class WorkflowPromptsMixin:
    def _build_main_prompt(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> str:
        return f"""
You are a nutrition decision-support assistant for gym users.
Build a 1-day meal plan using ONLY the retrieved candidate foods.

User profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Targets:
{json.dumps(targets, ensure_ascii=False, indent=2)}

Constraints:
- return exactly {request.meal_count} meals
- each item must use entity_id from the candidate list
- grams must be integer between 30 and 400
- respect excluded foods: {request.excluded_foods or []}
- must include these foods if possible: {request.must_include or []}
- ONLY use items where final_output_allowed=true
- use safe_display_name as the user-facing label; do not output raw source labels
- STRICTLY respect dietary_preference: if "vegetarian", ONLY use items with "vegetarian" or "vegan" in diet_tags. NEVER use chicken/meat/fish
- ALWAYS prefer cooked/prepared foods. NEVER use items containing "{RAW_FOOD_KEYWORD}" (raw) - these are base data only, user cannot eat raw rice/grains
- NEVER mention blocked base ingredients such as raw poultry, raw seafood, raw egg, raw grains, raw corn, raw tubers, or ambiguous raw produce
- do not use foods that violate allergy tags or dietary preference

Candidate foods:
{self.knowledge.format_candidates_for_prompt(candidates)}

Goal-aware anchor suggestions:
{self._format_candidate_anchor_summary(profile, candidates)}

Critical planning rules:
- never create a meal plan made only of vegetables or only low-calorie side dishes
- every meal must contribute meaningfully to calories and protein
- prefer must_include foods when they exist in the candidate list
- distribute calories close to the meal targets
- use 2 to 4 items per meal whenever the candidate list allows it

Return JSON only:
{{
  "summary": "short daily overview",
  "reasoning": ["grounded reason 1", "grounded reason 2"],
  "meals": [
    {{
      "meal_name": "Breakfast",
      "explanation": "why this meal fits the target",
      "items": [
        {{
          "entity_id": "food_123",
          "food_name": "candidate exact name",
          "grams": 150,
          "reason": "why selected"
        }}
      ]
    }}
  ]
}}
""".strip()

    def _build_revision_prompt(
        self,
        *,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        candidates: list[dict[str, Any]],
        previous_plan: Optional[dict[str, Any]],
        previous_raw: str,
        validation: Optional[dict[str, Any]],
        attempt: int,
    ) -> str:
        return f"""
You must repair the meal plan so that it passes numeric nutrition validation.
This is revision attempt {attempt}.

User profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Targets:
{json.dumps(targets, ensure_ascii=False, indent=2)}

Candidate foods:
{self.knowledge.format_candidates_for_prompt(candidates)}

CRITICAL REPAIR RULES (must follow):
- STRICTLY respect dietary_preference: vegetarian = only items with "vegetarian"/"vegan" in diet_tags. NO chicken/meat
- ALWAYS use cooked/prepared foods ONLY. NEVER select items with "{RAW_FOOD_KEYWORD}" in name (raw rice/grains are invalid for meal plans)
- ONLY keep items where final_output_allowed=true and use safe_display_name
- Fix ALL validation issues from the report above
- Keep grams 30-400, use only listed entity_ids

Previous plan JSON:
{json.dumps(previous_plan or {{}}, ensure_ascii=False, indent=2)}

Previous raw response:
{previous_raw}

Validation report:
{json.dumps(validation or {{}}, ensure_ascii=False, indent=2)}

Goal-aware anchor suggestions:
{self._format_candidate_anchor_summary(profile, candidates)}

Repair rules:
- keep the same JSON schema
- fix calories, protein, carbs, fat deviations first
- remove unresolved foods
- keep grams between 30 and 400
- respect dietary preference and allergies
- use only candidate entity_id values
- if calories or protein are too low, add higher-protein and higher-carb anchors from the candidate list
- do not repeat the same low-calorie vegetable across all meals

Return JSON only.
""".strip()

    def _build_pure_generation_prompt(
        self,
        profile: dict[str, Any],
        targets: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> str:
        return f"""
You are creating a pure-generation baseline for a gym nutrition system.
Do not use external retrieval context. Use your own general knowledge only.

Profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Targets:
{json.dumps(targets, ensure_ascii=False, indent=2)}

Return exactly {request.meal_count} meals and this JSON only:
{{
  "summary": "short daily overview",
  "reasoning": ["reason 1", "reason 2"],
  "meals": [
    {{
      "meal_name": "Breakfast",
      "explanation": "why this meal fits",
      "items": [
        {{
          "entity_id": null,
          "food_name": "common food name",
          "grams": 150,
          "reason": "why selected"
        }}
      ]
    }}
  ]
}}
""".strip()
