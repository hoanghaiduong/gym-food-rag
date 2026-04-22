from __future__ import annotations

from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent
from app.services.nutrition_knowledge_service import ascii_normalize
from app.services.nutrition_record_policy import DIRECT_EDIBLE_FRUIT_PATTERNS

from .constants import (
    DIET_LOCAL_SUPPLEMENT_HINTS,
    GOAL_SUPPORT_HINTS,
)

_DIRECT_EDIBLE_BUN_TUOI = "bun tuoi"
_DIRECT_EDIBLE_FRUIT_FAMILY = "fruit_family"
_DIRECT_EDIBLE_GENERIC_FRUIT_HINTS = {"trai cay", "hoa qua", "fruit"}
_PRODUCE_ONLY_LOCAL_HINTS = {"rau xanh", "trai cay", "hoa qua"}
_LOCAL_SUPPLEMENT_CHANNEL = "local_supplement"
_LOCAL_SUPPLEMENT_QUERY_LIMITS = {
    "must_include": 3,
    "preferred_food": 2,
    "bundle_query": 3,
    "diet_hint": 2,
    "goal_hint": 2,
}


class WorkflowCandidatePoolSupportMixin:
    def _is_produce_only_hint_request(
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
        return bool(normalized_hints) and all(hint in _PRODUCE_ONLY_LOCAL_HINTS for hint in normalized_hints)

    def _candidate_family_lookup_key(self, candidate: dict[str, Any]) -> str:
        return ascii_normalize(
            candidate.get("meal_family_key")
            or candidate.get("canonical_name_key")
            or candidate.get("safe_display_name")
            or candidate.get("name")
            or candidate.get("food_name")
        )

    def _candidate_exact_lookup_terms(self, candidate: dict[str, Any]) -> set[str]:
        terms: set[str] = set()
        for value in [
            candidate.get("name"),
            candidate.get("safe_display_name"),
            candidate.get("food_name"),
            candidate.get("meal_family_key"),
            candidate.get("canonical_name_key"),
            *(candidate.get("aliases") or []),
        ]:
            normalized = ascii_normalize(value)
            if normalized:
                terms.add(normalized)
        return terms

    def _candidate_is_direct_edible_fruit(self, candidate: dict[str, Any]) -> bool:
        haystack = " ".join(
            str(value)
            for value in [
                candidate.get("name"),
                candidate.get("safe_display_name"),
                candidate.get("food_name"),
                candidate.get("group_name"),
                candidate.get("meal_family_key"),
                candidate.get("canonical_name_key"),
            ]
            if value
        )
        normalized = ascii_normalize(haystack)
        if not normalized:
            return False
        if any(pattern in normalized for pattern in _DIRECT_EDIBLE_GENERIC_FRUIT_HINTS):
            return True
        return any(
            pattern in normalized
            for pattern in DIRECT_EDIBLE_FRUIT_PATTERNS
            if pattern not in _DIRECT_EDIBLE_GENERIC_FRUIT_HINTS
        )

    def _approved_direct_edible_hints_from_text(self, text: str) -> list[str]:
        normalized = ascii_normalize(text)
        if not normalized:
            return []

        hints: list[str] = []
        if _DIRECT_EDIBLE_BUN_TUOI in normalized:
            hints.append(_DIRECT_EDIBLE_BUN_TUOI)
        if any(pattern in normalized for pattern in _DIRECT_EDIBLE_GENERIC_FRUIT_HINTS):
            hints.append(_DIRECT_EDIBLE_FRUIT_FAMILY)
        for pattern in DIRECT_EDIBLE_FRUIT_PATTERNS:
            if pattern in _DIRECT_EDIBLE_GENERIC_FRUIT_HINTS or pattern not in normalized:
                continue
            hints.append(pattern)
        return self._unique_retrieval_terms(hints, limit=8)

    def _direct_edible_raw_allow_hints(
        self,
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent] = None,
    ) -> list[str]:
        hints: list[str] = []
        for value in request.must_include or []:
            hints.extend(self._approved_direct_edible_hints_from_text(value))
        if intent:
            for value in [
                *(intent.soft_preferences.must_include or []),
                *(intent.soft_preferences.preferred_foods or []),
            ]:
                hints.extend(self._approved_direct_edible_hints_from_text(value))
        hints.extend(self._approved_direct_edible_hints_from_text(request.instruction or ""))
        return self._unique_retrieval_terms(hints, limit=8)

    def _direct_edible_raw_candidate_matches_allow_hint(
        self,
        candidate: dict[str, Any],
        hint: str,
    ) -> bool:
        normalized_hint = ascii_normalize(hint)
        if not normalized_hint:
            return False
        if normalized_hint == _DIRECT_EDIBLE_BUN_TUOI:
            return any(
                term == _DIRECT_EDIBLE_BUN_TUOI or _DIRECT_EDIBLE_BUN_TUOI in term
                for term in self._candidate_exact_lookup_terms(candidate)
            )
        if normalized_hint == _DIRECT_EDIBLE_FRUIT_FAMILY:
            return self._candidate_is_direct_edible_fruit(candidate)
        return normalized_hint in self._candidate_exact_lookup_terms(candidate)

    def _annotate_local_supplement_candidate(
        self,
        candidate: dict[str, Any],
        *,
        source_kind: str,
        query: str,
    ) -> dict[str, Any]:
        annotated = dict(candidate)
        existing_channels = list(annotated.get("source_channels") or [])
        existing_queries = list(annotated.get("source_queries") or [])
        existing_purposes = list(annotated.get("source_query_purposes") or [])
        channel_values = [
            *existing_channels,
            _LOCAL_SUPPLEMENT_CHANNEL,
            f"{_LOCAL_SUPPLEMENT_CHANNEL}:{source_kind}",
        ]
        query_values = [*existing_queries, query]
        purpose_values = [*existing_purposes, f"local_{source_kind}"]
        annotated["source_channels"] = self._unique_retrieval_terms(channel_values, limit=8)
        annotated["source_queries"] = self._unique_retrieval_terms(query_values, limit=8)
        annotated["source_query_purposes"] = self._unique_retrieval_terms(purpose_values, limit=8)
        annotated["came_from_local_supplement"] = True
        annotated["local_supplement_source"] = source_kind
        return annotated

    def _merge_primary_and_supplement_candidates(
        self,
        primary_candidates: list[dict[str, Any]],
        supplement_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        def _candidate_key(item: dict[str, Any]) -> str:
            entity_id = ascii_normalize(item.get("entity_id"))
            if entity_id:
                return f"id:{entity_id}"
            return f"name:{ascii_normalize(item.get('name') or item.get('food_name'))}"

        for candidate in [*primary_candidates, *supplement_candidates]:
            key = _candidate_key(candidate)
            if not key or key.endswith(":"):
                continue
            current = merged.get(key)
            if current is None:
                merged[key] = dict(candidate)
                continue
            source_channels = self._unique_retrieval_terms(
                [
                    *(current.get("source_channels") or []),
                    *(candidate.get("source_channels") or []),
                ],
                limit=8,
            )
            source_queries = self._unique_retrieval_terms(
                [
                    *(current.get("source_queries") or []),
                    *(candidate.get("source_queries") or []),
                ],
                limit=8,
            )
            source_query_purposes = self._unique_retrieval_terms(
                [
                    *(current.get("source_query_purposes") or []),
                    *(candidate.get("source_query_purposes") or []),
                ],
                limit=8,
            )
            better = candidate
            if float(current.get("retrieval_score") or 0.0) >= float(candidate.get("retrieval_score") or 0.0):
                better = current
            merged[key] = {
                **better,
                "source_channels": source_channels,
                "source_queries": source_queries,
                "source_query_purposes": source_query_purposes,
                "came_from_local_supplement": bool(
                    current.get("came_from_local_supplement")
                    or candidate.get("came_from_local_supplement")
                ),
                "local_supplement_source": candidate.get("local_supplement_source")
                or current.get("local_supplement_source"),
            }
        return list(merged.values())

    def _pool_role_counts(self, candidates: list[dict[str, Any]], goal: str) -> dict[str, int]:
        role_counts = {"protein": 0, "carb": 0, "produce": 0}
        for candidate in candidates:
            role = self._candidate_role(candidate, goal)
            if role in role_counts:
                role_counts[role] += 1
        return role_counts

    def _pool_needs_local_supplement(
        self,
        candidates: list[dict[str, Any]],
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        intent: Optional[NutritionIntent] = None,
    ) -> bool:
        if len(candidates) < max(request.top_k, 12):
            return True

        goal = self._resolve_goal_family(profile, intent)
        role_counts = self._pool_role_counts(candidates, goal)
        produce_only_request = self._is_produce_only_hint_request(request, intent)
        must_include_candidates = self._collect_must_include_candidates(candidates, request)
        if produce_only_request:
            if role_counts["produce"] < min(max(len(request.must_include or []), 1), 2):
                return True
            return bool(request.must_include) and len(must_include_candidates) < min(len(request.must_include), 2)

        minimum_protein = 3 if self._is_plant_based_diet(profile.get("dietary_preference")) else 2
        if role_counts["protein"] < minimum_protein or role_counts["carb"] < 1:
            return True
        if self._requires_balanced_health_bias(
            request,
            intent,
            self._resolve_retrieval_strategy(profile, intent),
        ) and role_counts["produce"] < 1:
            return True

        return bool(request.must_include) and len(must_include_candidates) < min(len(request.must_include), 2)

    def _search_local_supplement_candidates(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        *,
        query: str,
        source_kind: str,
        limit: int,
        required_role_tags: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        results = self.knowledge.search_local_candidates(
            query,
            limit=limit,
            dietary_preference=profile.get("dietary_preference"),
            allergy_tags=profile.get("allergy_tags"),
            excluded_foods=request.excluded_foods,
            entity_types=["food"],
        )
        if required_role_tags:
            required_role_tag_set = set(required_role_tags)
            results = [
                candidate
                for candidate in results
                if required_role_tag_set.intersection(set(candidate.get("meal_role_tags") or []))
            ]
        return [
            self._annotate_local_supplement_candidate(
                candidate,
                source_kind=source_kind,
                query=query,
            )
            for candidate in results
        ]

    def _supplement_candidates_from_local(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        candidates: list[dict[str, Any]],
        intent: Optional[NutritionIntent] = None,
    ) -> list[dict[str, Any]]:
        del targets  # Supplement policy is driven by retrieval coverage, not macro targets.

        ranked_primary = self._sort_candidates_for_goal(candidates, profile, request, intent)
        filtered_primary = self._filter_candidates_for_meal_planning(ranked_primary, profile, request, intent)
        if not self._pool_needs_local_supplement(filtered_primary, profile, request, intent):
            return ranked_primary

        goal = self._resolve_goal_family(profile, intent)
        produce_only_request = self._is_produce_only_hint_request(request, intent)
        supplements: list[dict[str, Any]] = []

        for hint in request.must_include:
            per_variant_limit = (
                _LOCAL_SUPPLEMENT_QUERY_LIMITS["goal_hint"]
                if self._is_generic_support_hint(hint)
                else _LOCAL_SUPPLEMENT_QUERY_LIMITS["must_include"]
            )
            for variant in self._expand_hint_variants(hint):
                supplements.extend(
                    self._search_local_supplement_candidates(
                        profile,
                        request,
                        query=variant,
                        source_kind="must_include",
                        limit=per_variant_limit,
                        required_role_tags=["produce_support"]
                        if produce_only_request or ascii_normalize(hint) in _PRODUCE_ONLY_LOCAL_HINTS
                        else None,
                    )
                )

        if intent:
            for hint in intent.soft_preferences.preferred_foods[:3]:
                for variant in self._expand_hint_variants(hint):
                    supplements.extend(
                        self._search_local_supplement_candidates(
                            profile,
                            request,
                            query=variant,
                            source_kind="preferred_food",
                            limit=_LOCAL_SUPPLEMENT_QUERY_LIMITS["preferred_food"],
                            required_role_tags=["produce_support"]
                            if produce_only_request or ascii_normalize(hint) in _PRODUCE_ONLY_LOCAL_HINTS
                            else None,
                        )
                    )

        for query in self._build_local_supplement_queries(profile, request, intent)[:4]:
            supplements.extend(
                self._search_local_supplement_candidates(
                    profile,
                    request,
                    query=query,
                    source_kind="bundle_query",
                    limit=_LOCAL_SUPPLEMENT_QUERY_LIMITS["bundle_query"],
                    required_role_tags=["produce_support"] if produce_only_request else None,
                )
            )

        if not produce_only_request:
            diet_local_hints = self._prune_anchor_terms_for_allergies(
                DIET_LOCAL_SUPPLEMENT_HINTS.get(profile.get("dietary_preference") or "", []),
                profile.get("allergy_tags") or [],
            )
            for hint in diet_local_hints[:4]:
                supplements.extend(
                    self._search_local_supplement_candidates(
                        profile,
                        request,
                        query=hint,
                        source_kind="diet_hint",
                        limit=_LOCAL_SUPPLEMENT_QUERY_LIMITS["diet_hint"],
                    )
                )

            for hint in GOAL_SUPPORT_HINTS.get(goal, [])[:4]:
                for variant in self._expand_hint_variants(hint)[:2]:
                    supplements.extend(
                        self._search_local_supplement_candidates(
                            profile,
                            request,
                            query=variant,
                            source_kind="goal_hint",
                            limit=_LOCAL_SUPPLEMENT_QUERY_LIMITS["goal_hint"],
                        )
                    )

        if len(filtered_primary) < max(8, request.top_k // 2):
            backfill_candidates = list(
                self.knowledge.list_local_candidates(
                    limit=min(max(request.top_k, 12), 24),
                    dietary_preference=profile.get("dietary_preference"),
                    allergy_tags=profile.get("allergy_tags"),
                    excluded_foods=request.excluded_foods,
                    entity_types=["food"],
                )
            )
            if produce_only_request:
                backfill_candidates = [
                    candidate
                    for candidate in backfill_candidates
                    if "produce_support" in set(candidate.get("meal_role_tags") or [])
                ]
            supplements.extend(
                self._annotate_local_supplement_candidate(
                    candidate,
                    source_kind="backfill",
                    query="local_backfill",
                )
                for candidate in backfill_candidates
            )

        merged = self._merge_primary_and_supplement_candidates(candidates, supplements)
        return self._sort_candidates_for_goal(merged, profile, request, intent)

    def _apply_candidate_diversity_caps(
        self,
        selected: list[dict[str, Any]],
        ranked: list[dict[str, Any]],
        *,
        goal: str,
        request: NutritionRecommendationRequest,
        pool_limit: int,
        produce_cap: int,
        family_cap: int = 2,
    ) -> list[dict[str, Any]]:
        ordered_pool: list[dict[str, Any]] = []
        seen_entity_ids: set[str] = set()
        seen_names: set[str] = set()
        for candidate in [*selected, *ranked]:
            entity_id = candidate.get("entity_id")
            normalized_name = ascii_normalize(candidate.get("name"))
            if entity_id and entity_id in seen_entity_ids:
                continue
            if normalized_name and normalized_name in seen_names:
                continue
            ordered_pool.append(candidate)
            if entity_id:
                seen_entity_ids.add(entity_id)
            if normalized_name:
                seen_names.add(normalized_name)

        capped: list[dict[str, Any]] = []
        deferred: list[dict[str, Any]] = []
        family_counts: dict[str, int] = {}
        produce_count = 0

        for candidate in ordered_pool:
            family_key = self._candidate_family_lookup_key(candidate)
            role = self._candidate_role(candidate, goal)
            must_keep = any(
                self._candidate_matches_hint(candidate, hint)
                for hint in request.must_include
            )
            over_family_cap = bool(family_key and family_counts.get(family_key, 0) >= family_cap)
            over_produce_cap = role == "produce" and produce_count >= produce_cap
            if not must_keep and (over_family_cap or over_produce_cap):
                deferred.append(candidate)
                continue
            capped.append(candidate)
            if family_key:
                family_counts[family_key] = family_counts.get(family_key, 0) + 1
            if role == "produce":
                produce_count += 1
            if len(capped) >= pool_limit:
                return capped[:pool_limit]

        for candidate in deferred:
            capped.append(candidate)
            if len(capped) >= pool_limit:
                break
        return capped[:pool_limit]
