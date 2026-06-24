from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.ai_runtime_config import ai_runtime_config_service
from app.services.nutrition_knowledge_service import ascii_normalize

from .constants import (
    GOAL_RETRIEVAL_GUIDES,
    STRATEGY_RETRIEVAL_GUIDES,
)

_RETRIEVAL_REWRITE_CACHE_LIMIT = 256
_RETRIEVAL_QUERY_BUNDLE_CACHE_LIMIT = 128

_QUERY_SAFE_HINT_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "ca": ("fish seafood thuy san protein",),
    "ca ngu": ("tuna fish seafood protein",),
    "ca nuc": ("mackerel fish seafood protein",),
    "ga": ("chicken poultry protein",),
    "thit ga": ("chicken poultry protein",),
    "uc ga": ("chicken breast poultry protein",),
    "trung": ("egg protein",),
    "gao": ("com rice carb",),
    "com": ("gao rice carb",),
    "gao lut": ("brown rice carb",),
    "ngo": ("bap corn carb",),
    "bap": ("ngo corn carb",),
    "rau xanh": ("vegetable leafy greens rau luoc",),
    "trai cay": ("fruit apple banana mango guava produce",),
    "hoa qua": ("fruit apple banana mango guava produce",),
    "dau hu": ("dau phu tofu soy protein",),
    "dau phu": ("dau hu tofu soy protein",),
}
_PRODUCE_FOCUS_HINTS = {"rau xanh", "trai cay", "hoa qua"}
_PROTEIN_FOCUS_HINTS = {"ca", "ca ngu", "ca nuc", "ga", "thit ga", "uc ga", "trung", "dau hu", "dau phu"}
_CARB_FOCUS_HINTS = {"gao", "com", "gao lut", "ngo", "bap", "bun tuoi"}


class WorkflowRetrievalQueriesMixin:
    def _llm_retrieval_rewrite_enabled(self) -> bool:
        override = getattr(self, "_llm_retrieval_rewrite_enabled_override", None)
        if override is not None:
            return bool(override)
        runtime_value = ai_runtime_config_service.get_config().get("RETRIEVAL_ENABLE_LLM_QUERY_REWRITE")
        if runtime_value is not None:
            return str(runtime_value).strip().lower() in {"1", "true", "yes", "on"}
        return settings.RETRIEVAL_ENABLE_LLM_QUERY_REWRITE

    def _get_retrieval_instruction_rewrite_cache(self) -> dict[tuple[str, ...], str]:
        cache = getattr(self, "_retrieval_instruction_rewrite_cache", None)
        if cache is None:
            cache = {}
            setattr(self, "_retrieval_instruction_rewrite_cache", cache)
        return cache

    def _get_retrieval_query_bundle_cache(self) -> dict[tuple[str, ...], list[dict[str, Any]]]:
        cache = getattr(self, "_retrieval_query_bundle_cache", None)
        if cache is None:
            cache = {}
            setattr(self, "_retrieval_query_bundle_cache", cache)
        return cache

    def _cache_term_signature(self, values: list[str], *, limit: int = 6) -> tuple[str, ...]:
        unique_terms: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = ascii_normalize(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_terms.append(normalized)
            if len(unique_terms) >= limit:
                break
        return tuple(unique_terms)

    def _retrieval_rewrite_cache_key(
        self,
        instruction: str,
        intent: Optional[NutritionIntent] = None,
    ) -> tuple[str, ...]:
        return (
            ascii_normalize(instruction or ""),
            ascii_normalize(getattr(intent, "goal", "") or ""),
            ascii_normalize(getattr(intent, "planning_strategy", "") or ""),
        )

    def _retrieval_query_bundle_cache_key(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> tuple[str, ...]:
        return (
            ascii_normalize(request.instruction or ""),
            str(int(request.meal_count)),
            ascii_normalize(profile.get("dietary_preference") or ""),
            ascii_normalize(getattr(intent, "goal", "") or ""),
            ascii_normalize(getattr(intent, "planning_strategy", "") or ""),
            str(round(float(targets.get("daily_calories") or 0.0), 2)),
            str(round(float(targets.get("protein_g") or 0.0), 2)),
            str(round(float(targets.get("carbs_g") or 0.0), 2)),
            str(round(float(targets.get("fat_g") or 0.0), 2)),
            *self._cache_term_signature(list(request.must_include or []), limit=4),
            *self._cache_term_signature(list(request.excluded_foods or []), limit=4),
            *self._cache_term_signature(list(profile.get("allergy_tags") or []), limit=4),
        )

    def _expand_query_hint_term(self, value: str) -> str:
        normalized = ascii_normalize(value or "")
        if not normalized:
            return ""

        terms: list[str] = [normalized]
        extras = _QUERY_SAFE_HINT_EXPANSIONS.get(normalized)
        if extras:
            terms.extend(extras)
        else:
            expand_variants = getattr(self, "_expand_hint_variants", None)
            if callable(expand_variants):
                for variant in expand_variants(normalized)[:3]:
                    normalized_variant = ascii_normalize(variant)
                    if not normalized_variant or normalized_variant == normalized:
                        continue
                    terms.append(normalized_variant)
        return " ".join(self._unique_retrieval_terms(terms))

    def _expand_query_hint_terms(
        self,
        values: list[str],
        *,
        limit: Optional[int] = None,
    ) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        for value in values:
            phrase = self._expand_query_hint_term(value)
            normalized = ascii_normalize(phrase)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            expanded.append(phrase)
            if limit is not None and len(expanded) >= limit:
                break
        return expanded

    def _build_retrieval_queries(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> list[dict[str, Any]]:
        goal = self._resolve_goal_family(profile, intent)
        planning_strategy = self._resolve_retrieval_strategy(profile, intent)
        rerank_context = self._build_retrieval_rerank_context(profile, request, intent)
        guide = STRATEGY_RETRIEVAL_GUIDES.get(
            planning_strategy or "",
            GOAL_RETRIEVAL_GUIDES.get(goal, GOAL_RETRIEVAL_GUIDES["maintain"]),
        )
        diet = rerank_context["dietary_preference"]
        protein_anchors = rerank_context["protein_anchors"]
        carb_anchors = rerank_context["carb_anchors"]
        produce_anchors = rerank_context["produce_anchors"]
        balanced_anchors = rerank_context["balanced_anchors"]
        must_include = rerank_context["must_include"]
        preferred_foods = rerank_context["preferred_foods"]
        excluded = rerank_context["excluded_foods"]
        allergy_tags = rerank_context["allergy_tags"]
        expected_role_tags = rerank_context["expected_role_tags"]
        balanced_meal_required = bool(rerank_context.get("balanced_meal_required"))
        prioritized_must_include = self._prioritize_retrieval_terms(must_include, limit=4)
        calories = round(targets["daily_calories"])
        protein = round(targets["protein_g"])
        carbs = round(targets["carbs_g"])
        fat = round(targets["fat_g"])
        strategy_name = planning_strategy or goal
        protein_text = " ".join(self._expand_query_hint_terms(protein_anchors, limit=3))
        carb_text = " ".join(self._expand_query_hint_terms(carb_anchors, limit=1))
        produce_text = " ".join(self._expand_query_hint_terms(produce_anchors, limit=1))
        balanced_text = " ".join(self._expand_query_hint_terms(balanced_anchors, limit=1))
        balanced_meal_text = "balanced meal main dish staple protein vegetables" if balanced_meal_required else ""
        must_include_text = " ".join(self._expand_query_hint_terms(prioritized_must_include, limit=3))
        preferred_text = " ".join(self._expand_query_hint_terms(preferred_foods, limit=2))
        avoidance_text = " ".join(self._unique_retrieval_terms([*excluded, *allergy_tags], limit=5))
        normalized_must_include = [ascii_normalize(item) for item in prioritized_must_include if ascii_normalize(item)]
        explicit_produce_focus = bool(normalized_must_include) and all(
            hint in _PRODUCE_FOCUS_HINTS for hint in normalized_must_include
        )
        has_explicit_macro_anchor = any(
            hint in _PROTEIN_FOCUS_HINTS or hint in _CARB_FOCUS_HINTS
            for hint in normalized_must_include
        )
        produce_focus_only = explicit_produce_focus and not has_explicit_macro_anchor
        macro_query_parts = [
            strategy_name,
            "meal planning foods",
            diet,
            f"{calories} kcal",
            f"{protein}g protein",
            f"{carbs}g carbs",
            f"{fat}g fat",
            guide["macro_focus"],
            balanced_meal_text,
            protein_text,
            carb_text,
            produce_text,
            balanced_text,
        ]
        if produce_focus_only:
            macro_query_parts = [
                strategy_name,
                "produce meal planning foods",
                diet,
                f"{calories} kcal",
                guide["macro_focus"],
                must_include_text,
                produce_text or must_include_text,
                "fruit vegetables fiber micronutrients light meal",
            ]
        macro_query = " ".join(item for item in macro_query_parts if item).strip()
        queries: list[dict[str, Any]] = [
            {
                "channel": "macro_query",
                "query": macro_query,
                "expected_role_tags": expected_role_tags[:3],
                "query_purpose": "macro_goal",
            }
        ]

        role_tag_terms: dict[str, set[str]] = {
            "protein_anchor": set(protein_anchors) | set(balanced_anchors),
            "carb_anchor": set(carb_anchors),
            "produce_support": set(produce_anchors),
        }
        must_include_role_tags = [
            role_tag
            for role_tag, terms in role_tag_terms.items()
            if any(
                variant in terms
                for hint in prioritized_must_include
                for variant in self._expand_hint_variants(hint)
            )
        ]
        allow_produce_query_focus = "produce_support" in must_include_role_tags or not must_include_text
        shared_expected_role_tags = self._unique_retrieval_terms(
            (
                ["produce_support"]
                if produce_focus_only
                else [
                    "protein_anchor",
                    "carb_anchor",
                    *(["produce_support"] if allow_produce_query_focus and balanced_meal_required else []),
                ]
            ),
            limit=3,
        )
        produce_query_text = produce_text if allow_produce_query_focus else ""
        queries[0]["expected_role_tags"] = shared_expected_role_tags or expected_role_tags[:2]
        if must_include_text:
            must_include_query_parts = [
                strategy_name,
                diet,
                must_include_text,
                "meal foods",
                balanced_meal_text,
                protein_text,
                carb_text,
                preferred_text,
            ]
            if produce_focus_only:
                must_include_query_parts = [
                    strategy_name,
                    diet,
                    must_include_text,
                    "produce fruits vegetables meal foods",
                    "fiber micronutrients",
                    preferred_text,
                ]
            queries.append(
                {
                    "channel": "must_include_query",
                    "query": " ".join(item for item in must_include_query_parts if item).strip(),
                    "expected_role_tags": self._unique_retrieval_terms(
                        (["produce_support"] if produce_focus_only else must_include_role_tags or expected_role_tags[:2]),
                        limit=3,
                    ),
                    "query_purpose": "must_include",
                }
            )

        safe_query_parts = [
            "safe",
            strategy_name,
            diet,
            "foods",
            self._expand_query_hint_terms(protein_anchors, limit=1)[:1][0] if protein_anchors else "",
            carb_text,
            balanced_meal_text,
            produce_query_text,
            balanced_text,
        ]
        if produce_focus_only:
            safe_query_parts = [
                "safe",
                strategy_name,
                diet,
                "produce foods",
                must_include_text,
                produce_query_text or must_include_text,
                "fruit vegetables fiber",
            ]
        if avoidance_text:
            safe_query_parts.extend(["without", avoidance_text])
        queries.append(
            {
                "channel": "safe_guard_query",
                "query": " ".join(item for item in safe_query_parts if item).strip(),
                "expected_role_tags": shared_expected_role_tags or expected_role_tags[:2],
                "query_purpose": "safe_guard",
            }
        )

        role_specific_entry: Optional[dict[str, Any]] = None
        if produce_focus_only:
            role_specific_entry = {
                "channel": "role_query",
                "query": " ".join(
                    item
                    for item in [
                        "fruit vegetable produce foods",
                        diet,
                        must_include_text,
                        produce_query_text,
                        "micronutrients fiber",
                    ]
                    if item
                ).strip(),
                "expected_role_tags": ["produce_support"],
                "query_purpose": "role_specific",
            }
        elif balanced_meal_required:
            role_specific_entry = {
                "channel": "role_query",
                "query": " ".join(
                    item
                    for item in [
                        "balanced whole foods",
                        diet,
                        protein_text or balanced_text,
                        carb_text,
                        produce_query_text,
                    ]
                    if item
                ).strip(),
                "expected_role_tags": shared_expected_role_tags or ["protein_anchor", "carb_anchor"],
                "query_purpose": "role_specific",
            }
        elif rerank_context["post_workout_meal"]:
            role_specific_entry = {
                "channel": "role_query",
                "query": " ".join(
                    item
                    for item in [
                        "post workout recovery foods",
                        diet,
                        protein_text,
                        carb_text,
                    ]
                    if item
                ).strip(),
                "expected_role_tags": ["protein_anchor", "carb_anchor", "post_workout_friendly"],
                "query_purpose": "role_specific",
            }
        elif rerank_context["satiety_preference"] == "high":
            role_specific_entry = {
                "channel": "role_query",
                "query": " ".join(
                    item
                    for item in [
                        "high satiety foods",
                        diet,
                        protein_text,
                        produce_text,
                        "fiber",
                    ]
                    if item
                ).strip(),
                "expected_role_tags": ["protein_anchor", "produce_support", "high_satiety"],
                "query_purpose": "role_specific",
            }
        elif self._is_health_support_retrieval_intent(intent):
            role_specific_entry = {
                "channel": "role_query",
                "query": " ".join(
                    item
                    for item in [
                        "light digestion friendly foods",
                        diet,
                        protein_text,
                        carb_text,
                        produce_query_text,
                        "micronutrients",
                    ]
                    if item
                ).strip(),
                "expected_role_tags": shared_expected_role_tags or ["protein_anchor", "carb_anchor"],
                "query_purpose": "role_specific",
            }
        elif self._is_plant_based_diet(diet):
            role_specific_entry = {
                "channel": "role_query",
                "query": " ".join(
                    item
                    for item in [
                        "high protein plant foods",
                        diet,
                        protein_text,
                        "dau hu",
                        "dau nanh",
                        "dau lang",
                    ]
                    if item
                ).strip(),
                "expected_role_tags": ["protein_anchor"],
                "query_purpose": "role_specific",
            }
        if role_specific_entry:
            queries.append(role_specific_entry)

        unique_queries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query_entry in queries:
            normalized = ascii_normalize(query_entry.get("query"))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_queries.append(query_entry)
        return unique_queries[:4]

    def _is_complex_instruction(self, instruction: str, intent: Optional[NutritionIntent] = None) -> bool:
        """Intent-based + slang detection for rewrite (per feedback). Uses ascii_normalize for VN terms."""
        intent = intent if 'intent' in locals() else None  # Guard against NameError in all call paths
        if not instruction or len(instruction.strip()) < 8:
            return False
        instr_norm = ascii_normalize(instruction.lower())
        intent_goal = getattr(intent, 'goal', '') or ''
        planning = getattr(intent, 'planning_strategy', '') or ''
        complex_indicators = {"budget", "rẻ", "tiết kiệm", "healthy", "kiêng", "tăng cơ", "ít mỡ", "ăn kiêng", "fat loss", "eat healthier", "on a budget", "gym meal"}
        if any(k in instr_norm for k in complex_indicators):
            return True
        if intent and (intent_goal in ("lose_weight", "fat_loss", "eat_healthier") or "budget" in planning.lower()):
            return True
        # Avoid naive length; use semantic intent only
        return "slang" in instr_norm or any(term in instr_norm for term in ["ăn", "kiêng", "tăng", "mỡ"])

    def _rewrite_instruction_for_retrieval(
        self,
        instruction: str,
        intent: Optional[NutritionIntent] = None,
    ) -> str:
        """Hybrid query rewrite (before retrieval). LLM only for complex instructions; heuristic fallback for speed."""
        if not instruction or len(instruction.strip()) < 8:
            return instruction
        fallback = self._compact_instruction_for_retrieval(instruction)
        if not self._llm_retrieval_rewrite_enabled():
            return fallback
        if not self._is_complex_instruction(instruction, intent):
            return fallback

        cache_key = self._retrieval_rewrite_cache_key(instruction, intent)
        rewrite_cache = self._get_retrieval_instruction_rewrite_cache()
        cached = rewrite_cache.get(cache_key)
        if cached is not None:
            return cached

        prompt = f"""Rewrite user nutrition request into 10-15 effective keywords/phrases for Vietnamese food vector search.
Emphasize healthy budget options, high-protein low-fat, rau củ thịt nạc, practical gym meals, "ăn kiêng rẻ", "tăng cơ ít mỡ", "healthy on a budget".
Output ONLY comma-separated terms (no explanation, no quotes).

Request: {instruction}
Intent: {intent.goal if intent else 'general'} {intent.planning_strategy if intent else ''} budget healthy

Rewritten keywords:"""

        rewritten = fallback
        try:
            llm_rewritten = self.llm.generate_text(prompt, temperature=0.0).strip()
            if llm_rewritten and 5 < len(llm_rewritten) < 250:
                rewritten = llm_rewritten
        except Exception:
            pass
        if len(rewrite_cache) >= _RETRIEVAL_REWRITE_CACHE_LIMIT:
            rewrite_cache.clear()
        rewrite_cache[cache_key] = rewritten
        return rewritten

    def _build_retrieval_query_bundle(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> list[dict[str, Any]]:
        cache_key = self._retrieval_query_bundle_cache_key(profile, request, targets, intent)
        query_bundle_cache = self._get_retrieval_query_bundle_cache()
        cached = query_bundle_cache.get(cache_key)
        if cached is not None:
            return [dict(entry) for entry in cached]

        query_bundle = self._build_retrieval_queries(profile, request, targets, intent)
        if len(query_bundle_cache) >= _RETRIEVAL_QUERY_BUNDLE_CACHE_LIMIT:
            query_bundle_cache.clear()
        query_bundle_cache[cache_key] = [dict(entry) for entry in query_bundle]
        return query_bundle

    def _build_must_include_queries(
        self,
        must_include: list[str],
        rerank_context: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        must_include_terms = self._unique_retrieval_terms(must_include, limit=3)
        if not must_include_terms:
            return []

        rerank_context = rerank_context or {}
        strategy_name = rerank_context.get("planning_strategy") or ""
        diet = rerank_context.get("dietary_preference") or ""
        backup_anchors = self._unique_retrieval_terms(
            [
                *((rerank_context.get("protein_anchors") or [])[:2]),
                *((rerank_context.get("balanced_anchors") or [])[:1]),
                *((rerank_context.get("carb_anchors") or [])[:1]),
            ],
            limit=2,
        )
        expanded_must_include_terms = self._expand_query_hint_terms(must_include_terms, limit=3)
        expanded_backup_anchors = self._expand_query_hint_terms(backup_anchors, limit=2)

        queries = [
            " ".join(
                item for item in [strategy_name, diet, *expanded_must_include_terms, *expanded_backup_anchors] if item
            ).strip()
        ]
        for term in expanded_must_include_terms[:2]:
            queries.append(
                " ".join(item for item in [strategy_name, diet, term, *expanded_backup_anchors] if item).strip()
            )

        unique_queries: list[str] = []
        seen: set[str] = set()
        for query in queries:
            normalized = ascii_normalize(query)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_queries.append(query)
        return unique_queries[:5]
