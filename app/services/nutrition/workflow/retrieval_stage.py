from __future__ import annotations

from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent


class WorkflowRetrievalStageMixin:
    def _retrieve_candidates(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: dict[str, Any],
        intent: Optional[NutritionIntent] = None,
    ) -> list[dict[str, Any]]:
        rerank_context = self._build_retrieval_rerank_context(profile, request, intent)
        query_bundle = self._build_retrieval_query_bundle(profile, request, targets, intent)
        raw_limit = max(request.top_k * 3, 18)
        
        # ⭐ FIX 2: Two-pass retrieval to handle dietary_override
        dietary_override = profile.get("dietary_override", False)
        
        all_candidates: dict[str, dict[str, Any]] = {}
        
        # PASS 1: Retrieve must_include foods without dietary filter if override is set
        if request.must_include and dietary_override:
            must_include_queries = self._build_must_include_queries(request.must_include, rerank_context)
            must_include_candidates = self.knowledge.retrieve_candidates(
                queries=must_include_queries,
                limit=12,
                dietary_preference=None,  # ⭐ NO dietary filter
                allergy_tags=profile.get("allergy_tags"),
                excluded_foods=request.excluded_foods,
                entity_types=["food"],
                dietary_filter=False,  # ⭐ Explicit flag
                rerank_context=rerank_context,
            )
            for candidate in must_include_candidates:
                entity_id = candidate.get("entity_id")
                if entity_id:
                    all_candidates[entity_id] = candidate
        
        # PASS 2: Retrieve regular candidates with dietary filter
        regular_candidates = self.knowledge.retrieve_candidates(
            queries=query_bundle,
            limit=raw_limit,
            dietary_preference=profile.get("dietary_preference"),
            allergy_tags=profile.get("allergy_tags"),
            excluded_foods=request.excluded_foods,
            entity_types=["food"],
            dietary_filter=not dietary_override,  # Apply filter unless override
            rerank_context=rerank_context,
        )
        for candidate in regular_candidates:
            entity_id = candidate.get("entity_id")
            if entity_id:
                # Keep higher score version
                existing = all_candidates.get(entity_id)
                if not existing or (candidate.get("retrieval_score", 0) > existing.get("retrieval_score", 0)):
                    all_candidates[entity_id] = candidate
        
        candidates = list(all_candidates.values())
        candidates = self._optimize_candidate_pool(profile, request, targets, candidates, intent)
        
        if not candidates:
            raise ValueError("No foods were retrieved from Qdrant for the current profile.")
        return candidates
