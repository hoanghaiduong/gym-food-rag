from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.services.nutrition_knowledge_service import ascii_normalize, normalize_unicode_text

from .taxonomy import (
    ALLERGY_ALIASES,
    BUDGET_LEVEL_ALIASES,
    COOKING_COMPLEXITY_ALIASES,
    DIETARY_ALIASES,
    GOAL_ALIASES,
    MEAL_STYLE_ALIASES,
    PLANNING_STRATEGY_ALIASES,
    PRIORITY_ALIASES,
    RAW_SEMANTIC_GOAL_ALIASES,
    RAW_TO_DEFAULT_STRATEGY,
    RAW_TO_INTERNAL_GOAL,
    SATIETY_ALIASES,
)


class IntentNormalizationMixin:
    def _normalize_raw_semantic_goal(self, value: Any) -> str | None:
        normalized = ascii_normalize(str(value or "")).replace(" ", "_")
        if not normalized:
            return None
        if normalized in RAW_SEMANTIC_GOAL_ALIASES.values():
            return normalized
        return RAW_SEMANTIC_GOAL_ALIASES.get(normalized)

    def _normalize_internal_goal(self, value: Any) -> str | None:
        normalized = ascii_normalize(str(value or "")).replace(" ", "_")
        if not normalized:
            return None
        if normalized in GOAL_ALIASES.values():
            return normalized
        return GOAL_ALIASES.get(normalized)

    def _normalize_goal(self, value: Any) -> str | None:
        return self._normalize_internal_goal(value)

    def _normalize_planning_strategy(self, value: Any) -> str | None:
        normalized = ascii_normalize(str(value or "")).replace(" ", "_")
        if not normalized:
            return None
        if normalized in PLANNING_STRATEGY_ALIASES.values():
            return normalized
        return PLANNING_STRATEGY_ALIASES.get(normalized)

    def _goal_family_from_raw(self, raw_goal: str | None) -> str | None:
        if not raw_goal:
            return None
        return RAW_TO_INTERNAL_GOAL.get(raw_goal)

    def _goal_family_from_strategy(self, strategy: str | None) -> str | None:
        if not strategy:
            return None
        if strategy.startswith("surplus_"):
            return "gain_muscle"
        if strategy.startswith("deficit_"):
            return "lose_weight"
        if strategy.startswith("maintenance_"):
            return "maintain"
        return None

    def _default_raw_semantic_for_internal(self, internal_goal: str | None) -> str | None:
        return {
            "gain_muscle": "gain_muscle",
            "lose_weight": "fat_loss",
            "maintain": "maintain",
        }.get(internal_goal or "")

    def _default_strategy_for_goal(self, internal_goal: str | None) -> str | None:
        return {
            "gain_muscle": "surplus_high_protein",
            "lose_weight": "deficit_high_satiety",
            "maintain": "maintenance_balanced",
        }.get(internal_goal or "")

    def _infer_internal_goal(
        self,
        raw_goal: str | None,
        instruction: str,
        profile: dict[str, Any] | None = None,
    ) -> str | None:
        if raw_goal == "gain_weight_general":
            if self._any_phrase_in_text(instruction, ["tap", "gym", "protein", "sau tap", "phuc hoi"]):
                return "gain_muscle"
            return "gain_muscle"
        if raw_goal:
            mapped = self._goal_family_from_raw(raw_goal)
            if mapped:
                return mapped
        return self._normalize_goal((profile or {}).get("target_goal"))

    def _infer_planning_strategy(
        self,
        *,
        raw_goal: str | None,
        normalized_goal: str | None,
        instruction: str | None = None,
        priorities: list[str] | None = None,
        meal_preferences: dict[str, Any] | None = None,
        soft_preferences: dict[str, Any] | None = None,
    ) -> str | None:
        if raw_goal and RAW_TO_DEFAULT_STRATEGY.get(raw_goal):
            strategy = RAW_TO_DEFAULT_STRATEGY[raw_goal]
        else:
            strategy = self._default_strategy_for_goal(normalized_goal)

        priorities = priorities or []
        meal_preferences = meal_preferences or {}
        soft_preferences = soft_preferences or {}
        instruction = instruction or ""

        if normalized_goal == "gain_muscle":
            if raw_goal == "gain_weight_general":
                strategy = "surplus_balanced"
            if (
                raw_goal == "gain_muscle"
                or "protein" in priorities
                or "recovery" in priorities
                or bool(meal_preferences.get("post_workout_meal"))
                or self._any_phrase_in_text(instruction, ["gym", "tap", "sau tap", "phuc hoi", "post workout"])
            ):
                strategy = "surplus_high_protein"
        elif normalized_goal == "lose_weight":
            if raw_goal == "lose_weight_general":
                strategy = "deficit_balanced"
            if (
                raw_goal == "fat_loss"
                or "satiety" in priorities
                or soft_preferences.get("meal_style") == "light"
                or meal_preferences.get("satiety_preference") == "high"
            ):
                strategy = "deficit_high_satiety"
        elif normalized_goal == "maintain":
            if raw_goal == "support_training" or "recovery" in priorities or bool(meal_preferences.get("post_workout_meal")):
                strategy = "maintenance_training_support"
            elif raw_goal == "eat_healthier" or "micronutrients" in priorities or "digestion" in priorities:
                strategy = "maintenance_health_support"
            else:
                strategy = strategy or "maintenance_balanced"

        return self._normalize_planning_strategy(strategy)

    def _normalize_instruction(self, value: Any) -> str:
        raw_text = normalize_unicode_text(value)
        normalized = ascii_normalize(raw_text).lower()
        normalized = re.sub(r"[_/\\-]+", " ", normalized)
        normalized = re.sub(r"\bko\b|\bk\b", "khong", normalized)
        normalized = re.sub(r"\bkhong+\b", "khong", normalized)
        normalized = re.sub(r"\bmun\b", "muon", normalized)
        normalized = re.sub(r"\bta+ng\b", "tang", normalized)
        normalized = re.sub(r"\bgia+mm\b", "giam", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _phrase_present(
        self,
        instruction: str,
        phrase: str,
        *,
        single_threshold: float = 0.84,
        multi_threshold: float = 0.8,
    ) -> bool:
        normalized_instruction = self._normalize_instruction(instruction)
        normalized_phrase = self._normalize_instruction(phrase)
        if not normalized_instruction or not normalized_phrase:
            return False
        if normalized_phrase in normalized_instruction:
            return True

        instruction_tokens = normalized_instruction.split()
        phrase_tokens = normalized_phrase.split()
        if not instruction_tokens or not phrase_tokens:
            return False

        if len(phrase_tokens) == 1:
            target = phrase_tokens[0]
            if target in instruction_tokens:
                return True
            if len(target) <= 2:
                return False
            for token in instruction_tokens:
                if abs(len(token) - len(target)) > 2:
                    continue
                if SequenceMatcher(None, token, target).ratio() >= single_threshold:
                    return True
            return False

        window_sizes = {len(phrase_tokens)}
        if len(phrase_tokens) > 1:
            window_sizes.add(len(phrase_tokens) - 1)
        window_sizes.add(len(phrase_tokens) + 1)
        for window_size in sorted(size for size in window_sizes if 1 <= size <= len(instruction_tokens)):
            for idx in range(len(instruction_tokens) - window_size + 1):
                candidate = " ".join(instruction_tokens[idx : idx + window_size])
                if SequenceMatcher(None, candidate, normalized_phrase).ratio() >= multi_threshold:
                    return True
        return False

    def _any_phrase_in_text(self, instruction: str, phrases: list[str]) -> bool:
        return any(self._phrase_present(instruction, phrase) for phrase in phrases)

    def _exact_phrase_present(self, instruction: str, phrase: str) -> bool:
        normalized_instruction = self._normalize_instruction(instruction)
        normalized_phrase = self._normalize_instruction(phrase)
        if not normalized_instruction or not normalized_phrase:
            return False
        pattern = rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)"
        return bool(re.search(pattern, normalized_instruction))

    def _any_exact_phrase_in_text(self, instruction: str, phrases: list[str]) -> bool:
        return any(self._exact_phrase_present(instruction, phrase) for phrase in phrases)

    def _count_matching_phrases(self, instruction: str, phrases: list[str]) -> int:
        return sum(1 for phrase in phrases if self._phrase_present(instruction, phrase))

    def _normalize_dietary_preference(self, value: Any) -> str | None:
        normalized = ascii_normalize(str(value or "")).replace(" ", "_")
        if not normalized:
            return None
        if normalized in DIETARY_ALIASES.values():
            return normalized
        return DIETARY_ALIASES.get(normalized)

    def _normalize_allergies(self, value: Any) -> list[str]:
        raw_items: list[str]
        if value is None:
            return []
        if isinstance(value, list):
            raw_items = [str(item) for item in value]
        else:
            raw_items = re.split(r"[,;/]", str(value))
        normalized = []
        for item in raw_items:
            key = ascii_normalize(item).replace(" ", "_")
            if not key:
                continue
            normalized.append(ALLERGY_ALIASES.get(key, key if key in ALLERGY_ALIASES.values() else None))
        return self._merge_list([], [item for item in normalized if item])

    def _normalize_priorities(self, values: Any) -> list[str]:
        raw_items = values if isinstance(values, list) else [values] if values else []
        normalized = []
        for item in raw_items:
            key = ascii_normalize(str(item or "")).replace(" ", "_")
            if not key:
                continue
            normalized_priority = PRIORITY_ALIASES.get(key, key if key in PRIORITY_ALIASES.values() else None)
            if normalized_priority:
                normalized.append(normalized_priority)
        return self._merge_list([], normalized, max_items=6)

    def _normalize_choice(self, value: Any, aliases: dict[str, str]) -> str | None:
        normalized = ascii_normalize(str(value or "")).replace(" ", "_")
        if not normalized:
            return None
        return aliases.get(normalized, normalized if normalized in aliases.values() else None)

    def _normalize_meal_count(self, value: Any) -> int | None:
        try:
            meal_count = int(value)
        except (TypeError, ValueError):
            return None
        return meal_count if 3 <= meal_count <= 5 else None

    def _normalize_confidence(self, value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(confidence, 1.0))

    def _clean_food_list(self, values: Any, *, max_items: int = 8) -> list[str]:
        if values is None:
            return []
        if isinstance(values, list):
            raw_items = values
        else:
            raw_items = re.split(r"[,;/]", str(values))
        cleaned = []
        for item in raw_items:
            text = str(item).strip()
            if not text:
                continue
            text = re.sub(r"\s+", " ", text)
            cleaned.append(text)
        return self._merge_list([], cleaned, max_items=max_items)

    def _merge_list(self, base: list[str], overlay: list[str], *, max_items: int = 12) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*(base or []), *(overlay or [])]:
            text = str(item).strip()
            normalized = ascii_normalize(text)
            if not text or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(text)
            if len(merged) >= max_items:
                break
        return merged
