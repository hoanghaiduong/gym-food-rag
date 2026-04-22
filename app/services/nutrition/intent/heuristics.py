from __future__ import annotations

import re
from typing import Any

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize

from .taxonomy import (
    ALLERGY_ALIASES,
    BUDGET_LEVEL_ALIASES,
    COOKING_COMPLEXITY_ALIASES,
    DIETARY_ALIASES,
    MEAL_STYLE_ALIASES,
    PRIORITY_HINTS,
    RAW_SEMANTIC_GOAL_HINTS,
    SATIETY_ALIASES,
)


class IntentHeuristicsMixin:
    def _build_default_intent(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> NutritionIntent:
        goal = self._normalize_goal(profile.get("target_goal"))
        raw_goal = self._normalize_raw_semantic_goal(profile.get("goal_raw_semantic")) or self._default_raw_semantic_for_internal(goal)
        strategy = self._normalize_planning_strategy(profile.get("planning_strategy")) or self._default_strategy_for_goal(goal)
        dietary_preference = self._normalize_dietary_preference(profile.get("dietary_preference"))
        allergies = self._normalize_allergies(profile.get("allergy_tags") or profile.get("allergies"))

        default_priorities = [] if request.instruction else {
            "gain_muscle": ["protein", "recovery"],
            "lose_weight": ["protein", "satiety", "lightness"],
            "maintain": ["variety", "micronutrients"],
        }.get(goal or "maintain", ["variety"])

        return NutritionIntent(
            goal_raw_semantic=raw_goal,
            goal_normalized_internal=goal,
            planning_strategy=strategy,
            goal=goal,
            priorities=default_priorities,
            hard_constraints={
                "dietary_preference": dietary_preference,
                "allergies": allergies,
                "must_avoid": self._clean_food_list(request.excluded_foods),
            },
            soft_preferences={
                "must_include": self._clean_food_list(request.must_include),
                "preferred_foods": [],
                "disliked_foods": [],
                "cooking_complexity": None,
                "budget_level": None,
                "meal_style": None,
            },
            meal_preferences={
                "meal_count": request.meal_count,
                "pre_workout_meal": False,
                "post_workout_meal": False,
                "late_dinner": False,
                "satiety_preference": None,
            },
            notes=[],
            confidence=0.55,
            source="profile_request_defaults",
        )

    def _build_heuristic_intent(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> NutritionIntent:
        instruction = self._normalize_instruction(request.instruction or "")
        raw_goal = self._detect_raw_semantic_goal(instruction)
        normalized_goal = self._normalize_internal_goal(self._infer_internal_goal(raw_goal, instruction, profile))
        strategy = self._infer_planning_strategy(raw_goal=raw_goal, normalized_goal=normalized_goal, instruction=instruction)
        payload: dict[str, Any] = {
            "goal_raw_semantic": raw_goal,
            "goal_normalized_internal": normalized_goal,
            "planning_strategy": strategy,
            "goal": normalized_goal,
            "priorities": self._detect_priorities(instruction),
            "hard_constraints": {
                "dietary_preference": self._detect_dietary_preference(instruction),
                "allergies": self._detect_allergies(instruction),
                "must_avoid": self._detect_food_mentions(
                    instruction,
                    triggers=["tranh", "khong an", "khong dung", "loai bo", "khong muon an"],
                ),
            },
            "soft_preferences": {
                "must_include": self._detect_food_mentions(instruction, triggers=["phai co", "bat buoc co", "must include", "can co"]),
                "preferred_foods": self._detect_food_mentions(instruction, triggers=["uu tien", "thich", "prefer", "tap trung vao"]),
                "disliked_foods": self._detect_food_mentions(instruction, triggers=["khong thich", "ghet", "khong muon"]),
                "cooking_complexity": self._detect_choice(
                    instruction,
                    COOKING_COMPLEXITY_ALIASES,
                    {"de_nau": ["de nau", "de lam", "nhanh", "it che bien"], "medium": ["vua"], "any": ["bat ky", "gi cung duoc"]},
                ),
                "budget_level": self._detect_choice(
                    instruction,
                    BUDGET_LEVEL_ALIASES,
                    {"ngan_sach": ["ngan sach", "gia re", "tiet kiem"], "cao_cap": ["cao cap", "premium"]},
                ),
                "meal_style": self._detect_choice(
                    instruction,
                    MEAL_STYLE_ALIASES,
                    {
                        "high_protein": ["protein cao", "giau dam", "high protein"],
                        "simple": ["don gian", "de nau", "de lam"],
                        "traditional": ["truyen thong", "mon viet"],
                        "thanh_dam": ["thanh dam", "nhe bung"],
                        "can_bang": ["can bang", "balanced"],
                    },
                ),
            },
            "meal_preferences": {
                "meal_count": self._detect_meal_count(instruction),
                "pre_workout_meal": self._any_phrase_in_text(instruction, ["truoc tap", "pre workout"]),
                "post_workout_meal": self._any_phrase_in_text(instruction, ["sau tap", "post workout", "phuc hoi"]),
                "late_dinner": self._any_phrase_in_text(instruction, ["toi muon", "an dem", "late dinner"]),
                "satiety_preference": self._detect_choice(
                    instruction,
                    SATIETY_ALIASES,
                    {"no_lau": ["no lau", "khong doi", "no bung"], "light": ["nhe bung", "light"]},
                ),
            },
            "notes": [],
            "confidence": 0.45 if request.instruction else 0.0,
            "source": "heuristic_parser",
        }
        payload = self._apply_semantic_defaults(payload, instruction=instruction, raw_goal=raw_goal, normalized_goal=normalized_goal)

        if payload["meal_preferences"]["post_workout_meal"]:
            payload["priorities"] = self._merge_list(payload["priorities"], ["recovery", "protein"])
        if payload["meal_preferences"]["satiety_preference"] == "high":
            payload["priorities"] = self._merge_list(payload["priorities"], ["satiety"])
        if payload["soft_preferences"]["cooking_complexity"] == "easy":
            payload["priorities"] = self._merge_list(payload["priorities"], ["simplicity"])
        if payload["soft_preferences"]["budget_level"] == "low":
            payload["priorities"] = self._merge_list(payload["priorities"], ["budget"])

        normalized = self._normalize_payload(payload, source="heuristic_parser")
        if normalized.goal_normalized_internal and normalized.goal_normalized_internal != self._normalize_goal(profile.get("target_goal")):
            normalized.notes = self._merge_list(normalized.notes, [f"goal_override:{normalized.goal_normalized_internal}"])
        return normalized

    def _detect_raw_semantic_goal(self, instruction: str) -> str | None:
        if self._any_exact_phrase_in_text(instruction, ["tang can", "len can", "hoi gay", "day hon", "day dan hon", "tang can sach"]):
            return "gain_weight_general"
        if self._any_phrase_in_text(instruction, ["bulk", "bulking", "tang co", "len co", "xay co", "muscle gain", "gain muscle"]):
            return "gain_muscle"
        if self._any_phrase_in_text(instruction, ["hieu suat tap luyen", "ho tro tap luyen", "tap co suc", "tap tot hon", "phuc hoi sau tap", "bua sau tap"]):
            return "support_training"
        if self._any_phrase_in_text(instruction, ["giam mo", "siet mo", "cutting", "no lau", "khong doi", "khong bi doi"]):
            return "fat_loss"
        if self._any_phrase_in_text(instruction, ["an lanh manh", "an khoe", "an sach", "tot cho suc khoe", "khoe hon"]):
            return "eat_healthier"

        matches: dict[str, int] = {}
        for goal, hints in RAW_SEMANTIC_GOAL_HINTS.items():
            score = self._count_matching_phrases(instruction, hints)
            if score:
                matches[goal] = score

        if not matches:
            return None
        if "gain_muscle" in matches and self._any_phrase_in_text(instruction, ["tap", "gym", "protein", "phuc hoi", "sau tap"]):
            return "gain_muscle"
        if "fat_loss" in matches and self._any_phrase_in_text(instruction, ["no lau", "khong doi", "no bung"]):
            return "fat_loss"
        return max(matches.items(), key=lambda item: item[1])[0]

    def _detect_goal(self, instruction: str) -> str | None:
        raw_goal = self._detect_raw_semantic_goal(instruction)
        if not raw_goal:
            return None
        return self._goal_family_from_raw(raw_goal)

    def _detect_priorities(self, instruction: str) -> list[str]:
        priorities: list[str] = []
        for priority, hints in PRIORITY_HINTS.items():
            if self._any_exact_phrase_in_text(instruction, hints):
                priorities.append(priority)
        return priorities

    def _detect_dietary_preference(self, instruction: str) -> str | None:
        if self._any_exact_phrase_in_text(instruction, ["an chay thuan", "chay thuan", "thuan chay", "vegan"]):
            return "vegan"
        if self._any_exact_phrase_in_text(instruction, ["an chay", "vegetarian"]):
            return "vegetarian"
        if self._any_exact_phrase_in_text(instruction, ["khong an ca", "tranh ca", "khong dung ca", "loai bo ca"]):
            return None
        if self._any_exact_phrase_in_text(instruction, ["an ca", "pescatarian"]):
            return "pescatarian"
        for raw, normalized in DIETARY_ALIASES.items():
            if normalized in {"vegan", "pescatarian"}:
                continue
            if self._phrase_present(instruction, raw.replace("_", " ")):
                return normalized
        if self._phrase_present(instruction, "an chay"):
            return "vegetarian"
        return None

    def _detect_allergies(self, instruction: str) -> list[str]:
        allergy_triggers = ["di ung", "allergy", "khong an duoc", "khong hop"]
        if not self._any_exact_phrase_in_text(instruction, allergy_triggers):
            return []
        tags = []
        for segment in re.split(r"[,.;\n]", instruction):
            if not self._any_exact_phrase_in_text(segment, allergy_triggers):
                continue
            for raw, normalized in ALLERGY_ALIASES.items():
                if self._exact_phrase_present(segment, raw.replace("_", " ")):
                    tags.append(normalized)
        return self._merge_list([], tags)

    def _detect_meal_count(self, instruction: str) -> int | None:
        matches = re.findall(r"\b([3-5])\s*(bua|meal|mon)\b", instruction)
        if not matches:
            return None
        return self._normalize_meal_count(matches[-1][0])

    def _detect_food_mentions(self, instruction: str, *, triggers: list[str]) -> list[str]:
        candidates: list[str] = []
        segments = re.split(r"[.;\n]", instruction)
        for segment in segments:
            normalized_segment = segment.strip()
            if not normalized_segment:
                continue
            if "khong an ca" in normalized_segment or "tranh ca" in normalized_segment:
                candidates.append("ca")
            if not any(trigger in normalized_segment for trigger in triggers):
                continue
            after_trigger = normalized_segment
            for trigger in triggers:
                if trigger in after_trigger:
                    after_trigger = after_trigger.split(trigger, 1)[1]
                    break
            parts = re.split(r",| va | voi | hoac | / ", after_trigger)
            cleaned_parts = []
            for part in parts:
                cleaned = part.strip(" :-")
                if len(cleaned) < 3:
                    continue
                if any(
                    token in cleaned
                    for token in [
                        "bua",
                        "thuc don",
                        "calo",
                        "macro",
                        "gram",
                        "protein",
                        "carb",
                        "fat",
                        "de nau",
                        "de lam",
                        "de mua",
                        "tiet kiem",
                        "ngan sach",
                        "thanh dam",
                        "de tieu",
                        "di ung",
                        "uu tien",
                    ]
                ):
                    continue
                cleaned_parts.append(cleaned)
            candidates.extend(cleaned_parts[:3])
        return self._clean_food_list(candidates)

    def _detect_choice(self, instruction: str, aliases: dict[str, str], hints: dict[str, list[str]]) -> str | None:
        for raw, phrases in hints.items():
            if self._any_exact_phrase_in_text(instruction, phrases):
                return aliases.get(raw, aliases.get(ascii_normalize(raw), raw))
        return None

    def _apply_semantic_defaults(
        self,
        payload: dict[str, Any],
        *,
        instruction: str,
        raw_goal: str | None,
        normalized_goal: str | None,
    ) -> dict[str, Any]:
        priorities = payload.get("priorities") or []
        meal_preferences = payload.get("meal_preferences") or {}

        if normalized_goal == "gain_muscle":
            priorities = self._merge_list(priorities, ["protein"])
            if raw_goal == "gain_muscle" or self._any_phrase_in_text(instruction, ["tap", "gym", "protein", "phuc hoi", "sau tap", "post workout"]):
                priorities = self._merge_list(priorities, ["recovery"])
                meal_preferences["post_workout_meal"] = True
        elif normalized_goal == "lose_weight":
            if raw_goal == "lose_weight_general" or self._any_exact_phrase_in_text(instruction, ["nhe nhang", "nhe bung", "thanh dam", "it dau mo"]):
                priorities = self._merge_list(priorities, ["lightness"])
            if raw_goal == "fat_loss" or self._any_phrase_in_text(instruction, ["khong doi", "no lau", "no bung", "it doi"]):
                priorities = self._merge_list(priorities, ["satiety"])
                meal_preferences["satiety_preference"] = meal_preferences.get("satiety_preference") or "high"
        elif normalized_goal == "maintain":
            if raw_goal == "eat_healthier":
                priorities = self._merge_list(priorities, ["micronutrients", "variety"])
            if raw_goal == "support_training":
                priorities = self._merge_list(priorities, ["recovery", "protein"])
                meal_preferences["post_workout_meal"] = True

        payload["priorities"] = priorities
        payload["meal_preferences"] = meal_preferences
        return payload

    def _detect_dietary_override(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        intent: NutritionIntent,
    ) -> bool:
        dietary_pref = str(profile.get("dietary_preference") or "").lower()
        if dietary_pref not in ["vegetarian", "vegan"]:
            return False

        meat_keywords = [
            "ga", "thit", "beef", "chicken", "pork", "ca", "fish",
            "tom", "tep", "shrimp", "prawn", "ut", "uc", "thá»‹t",
            "gÃ ", "cÃ¡", "tÃ´m", "tÃ©p", "heo", "bo", "vit", "ngan",
        ]
        for hint in request.must_include:
            hint_normalized = ascii_normalize(hint).lower()
            if any(keyword in hint_normalized for keyword in meat_keywords):
                return True
        return False
