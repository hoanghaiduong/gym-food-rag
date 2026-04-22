from __future__ import annotations

from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize

from .constants import (
    COMMON_FOOD_HINTS,
    COOKED_STAPLE_SUPPORT_HINTS,
    DIET_LOCAL_SUPPLEMENT_HINTS,
    GENERIC_SUPPORT_HINTS,
    RAW_STAPLE_HINTS,
)

_PRODUCE_ONLY_SUPPLEMENT_HINTS = {"rau xanh", "trai cay", "hoa qua"}


class WorkflowRetrievalSupportQueriesMixin:
    def _is_produce_only_supplement_request(
        self,
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent] = None,
    ) -> bool:
        normalized_hints = self._unique_retrieval_terms(
            [
                *(request.must_include or []),
                *((intent.soft_preferences.must_include or []) if intent else []),
            ],
            limit=6,
        )
        return bool(normalized_hints) and all(hint in _PRODUCE_ONLY_SUPPLEMENT_HINTS for hint in normalized_hints)

    def _expand_hint_variants(self, hint: str) -> list[str]:
        normalized_hint = ascii_normalize(hint)
        if not normalized_hint:
            return []
        variants: list[str] = [normalized_hint]
        seen: set[str] = {normalized_hint}
        for key, extra_variants in COMMON_FOOD_HINTS.items():
            if normalized_hint == key or normalized_hint in key or key in normalized_hint:
                for variant in extra_variants:
                    normalized_variant = ascii_normalize(variant)
                    if not normalized_variant or normalized_variant in seen:
                        continue
                    seen.add(normalized_variant)
                    variants.append(normalized_variant)
        return variants

    def _is_generic_support_hint(self, hint: str) -> bool:
        return ascii_normalize(hint) in GENERIC_SUPPORT_HINTS

    def _build_local_supplement_queries(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent] = None,
    ) -> list[str]:
        rerank_context = self._build_retrieval_rerank_context(profile, request, intent)
        strategy = rerank_context.get("planning_strategy") or ""
        protein_anchors = rerank_context.get("protein_anchors") or []
        carb_anchors = rerank_context.get("carb_anchors") or []
        produce_anchors = rerank_context.get("produce_anchors") or []
        must_include = rerank_context.get("must_include") or []
        if self._is_produce_only_supplement_request(request, intent):
            produce_queries = [
                *must_include,
                *produce_anchors[:3],
            ]
            unique_queries: list[str] = []
            seen: set[str] = set()
            for query in produce_queries:
                normalized = ascii_normalize(query)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                unique_queries.append(normalized)
            return unique_queries[:6]

        safe_carb_anchors = [
            anchor
            for anchor in carb_anchors
            if ascii_normalize(anchor) not in RAW_STAPLE_HINTS
        ]
        fallback_carb_anchors = safe_carb_anchors or COOKED_STAPLE_SUPPORT_HINTS

        queries: list[str] = []
        queries.extend(protein_anchors[:3])
        queries.extend(fallback_carb_anchors[:2])
        diet_supplement_hints = self._prune_anchor_terms_for_allergies(
            DIET_LOCAL_SUPPLEMENT_HINTS.get(rerank_context.get("dietary_preference") or "", []),
            rerank_context.get("allergy_tags") or [],
        )
        queries.extend(diet_supplement_hints[:5])
        if any(ascii_normalize(anchor) in RAW_STAPLE_HINTS for anchor in carb_anchors):
            queries.extend(COOKED_STAPLE_SUPPORT_HINTS[:4])

        first_composite_anchor = ""
        primary_carb_anchor = fallback_carb_anchors[0] if fallback_carb_anchors else ""
        for protein_anchor in protein_anchors[:3]:
            normalized_anchor = ascii_normalize(protein_anchor)
            if not normalized_anchor or (len(normalized_anchor) <= 2 and " " not in normalized_anchor):
                continue
            if not first_composite_anchor:
                first_composite_anchor = normalized_anchor
            if primary_carb_anchor:
                queries.append(f"{normalized_anchor} {primary_carb_anchor}")
            if produce_anchors:
                queries.append(f"{normalized_anchor} {produce_anchors[0]}")

        if "thit ga" in protein_anchors:
            if "gao" in must_include or "com" in must_include or carb_anchors:
                queries.extend(["thit ga com", "thit ga khoai lang"])
            queries.append("thit ga pho")

        if any(ascii_normalize(anchor) in {"ngo", "bap", "corn"} for anchor in [*must_include, *carb_anchors]):
            queries.extend(["ngo luoc", "ngo hap", "ngo nuong"])

        if strategy in {"maintenance_training_support", "surplus_high_protein"} and first_composite_anchor and primary_carb_anchor:
            queries.append(f"{first_composite_anchor} {primary_carb_anchor}")

        unique_queries: list[str] = []
        seen: set[str] = set()
        for query in queries:
            normalized = ascii_normalize(query)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_queries.append(normalized)
        return unique_queries[:8]
