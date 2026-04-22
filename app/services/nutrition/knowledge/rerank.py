from __future__ import annotations

import math
from typing import Any, Iterable, Optional

from app.core.config import settings

from .normalize import ascii_normalize, safe_float


class RerankMixin:
    def _normalize_scores(self, values: list[float]) -> list[float]:
        if not values:
            return []
        low = min(values)
        high = max(values)
        if math.isclose(low, high):
            return [1.0 for _ in values]
        return [(value - low) / (high - low) for value in values]

    def _name_overlap_score(self, query: str, payload: dict[str, Any]) -> float:
        query_tokens = set(ascii_normalize(query).split())
        candidate_text = " ".join(
            str(item)
            for item in [
                payload.get("name"),
                payload.get("name_en"),
                *(payload.get("aliases") or []),
                payload.get("group_name"),
                payload.get("category_slug"),
            ]
            if item
        )
        candidate_tokens = set(ascii_normalize(candidate_text).split())
        if not query_tokens or not candidate_tokens:
            return 0.0
        return len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)

    def _payload_anchor_text(self, payload: dict[str, Any]) -> str:
        return " ".join(
            str(item)
            for item in [
                payload.get("name"),
                payload.get("name_en"),
                *(payload.get("aliases") or []),
                payload.get("group_name"),
                payload.get("category_slug"),
                " ".join(payload.get("ingredient_hints") or []),
                " ".join(payload.get("meal_role_tags") or []),
            ]
            if item
        )

    def _phrase_alignment_score(self, payload: dict[str, Any], phrases: Iterable[str]) -> float:
        normalized_phrases = [ascii_normalize(phrase) for phrase in phrases if ascii_normalize(phrase)]
        if not normalized_phrases:
            return 0.0

        normalized_text = ascii_normalize(self._payload_anchor_text(payload))
        candidate_tokens = set(normalized_text.split())
        matches = 0
        for phrase in normalized_phrases:
            phrase_tokens = set(phrase.split())
            if phrase in normalized_text or (phrase_tokens and phrase_tokens.issubset(candidate_tokens)):
                matches += 1
        return matches / max(len(normalized_phrases), 1)

    def _must_include_score(self, payload: dict[str, Any], must_include: Iterable[str]) -> float:
        return 1.0 if self._phrase_alignment_score(payload, must_include) > 0.0 else 0.0

    def _role_alignment_score(self, payload: dict[str, Any], expected_role_tags: Iterable[str]) -> float:
        expected = {ascii_normalize(tag) for tag in expected_role_tags if ascii_normalize(tag)}
        if not expected:
            return 0.0
        observed = {ascii_normalize(tag) for tag in (payload.get("meal_role_tags") or []) if ascii_normalize(tag)}
        return len(expected & observed) / max(len(expected), 1)

    def _generic_penalty(
        self,
        payload: dict[str, Any],
        rerank_context: Optional[dict[str, Any]],
        *,
        anchor_match_score: float,
        must_include_score: float,
    ) -> float:
        if not rerank_context:
            return 0.0

        expected_roles = {
            ascii_normalize(tag)
            for tag in (rerank_context.get("expected_role_tags") or [])
            if ascii_normalize(tag)
        }
        balanced_meal_required = bool(rerank_context.get("balanced_meal_required"))
        if "protein_anchor" not in expected_roles and not balanced_meal_required:
            return 0.0

        role_tags = {ascii_normalize(tag) for tag in (payload.get("meal_role_tags") or []) if ascii_normalize(tag)}
        if anchor_match_score > 0.0 or must_include_score > 0.0:
            return 0.0

        normalized_name = ascii_normalize(payload.get("name") or payload.get("food_name"))
        normalized_group = ascii_normalize(payload.get("group_name"))
        diet_tags = {ascii_normalize(tag) for tag in (payload.get("diet_tags") or []) if ascii_normalize(tag)}
        protein = safe_float(payload.get("protein_g"), 0.0)
        carbs = safe_float(payload.get("carbs_g"), 0.0)
        protein_anchor_terms = [*((rerank_context.get("protein_anchors") or [])[:3]), *((rerank_context.get("balanced_anchors") or [])[:2])]
        explicit_anchor_phrase = self._phrase_alignment_score(payload, protein_anchor_terms) > 0.0
        produce_like = bool(
            "produce_support" in role_tags
            or "rau" in normalized_group
            or "trai cay" in normalized_group
            or "qua chin" in normalized_group
            or normalized_name.startswith(("rau ", "qua ", "trai "))
            or ("produce" in diet_tags and "hat" not in normalized_group and "sua" not in normalized_group)
        )

        if produce_like and not explicit_anchor_phrase:
            if balanced_meal_required or "protein_anchor" in expected_roles:
                return 1.0
            if protein < 12 and carbs < 25:
                return 1.0

        if "protein_anchor" in role_tags and explicit_anchor_phrase:
            return 0.0
        if role_tags & {"produce_support", "carb_anchor"}:
            return 1.0
        return 0.0

    def _rerank_points(self, query: str, points: list[Any], *, limit: int) -> list[dict[str, Any]]:
        if not points:
            return []

        candidate_limit = max(limit, settings.RETRIEVAL_RERANK_CANDIDATES)
        trimmed_points = points[:candidate_limit]
        base_scores = [float(point.score or 0.0) for point in trimmed_points]
        payloads = [point.payload for point in trimmed_points]
        documents = [
            payload.get("hybrid_text") or payload.get("dense_text") or payload.get("content") or payload.get("name") or ""
            for payload in payloads
        ]
        rerank_scores = self.embedder.rerank_documents(query, documents) if settings.RETRIEVAL_ENABLE_RERANK else [0.0 for _ in documents]
        quality_scores = [safe_float(payload.get("quality_score"), 0.0) for payload in payloads]
        overlap_scores = [self._name_overlap_score(query, payload) for payload in payloads]
        planner_weights = [safe_float(payload.get("planner_rank_weight"), 0.0) for payload in payloads]

        normalized_base = self._normalize_scores(base_scores)
        normalized_rerank = self._normalize_scores(rerank_scores)

        ranked_items = []
        for point, base_score, rerank_score, quality_score, overlap_score, planner_weight in zip(
            trimmed_points,
            normalized_base,
            normalized_rerank,
            quality_scores,
            overlap_scores,
            planner_weights,
        ):
            if settings.RETRIEVAL_ENABLE_RERANK:
                final_score = 0.30 * base_score + 0.40 * rerank_score + 0.15 * quality_score + 0.08 * overlap_score + 0.07 * planner_weight
            else:
                final_score = 0.48 * base_score + 0.22 * quality_score + 0.16 * overlap_score + 0.14 * planner_weight
            ranked_items.append(
                {
                    "payload": point.payload,
                    "score": round(final_score, 6),
                    "base_score": round(float(point.score or 0.0), 6),
                    "rerank_score": round(rerank_score, 6),
                    "quality_score": round(float(quality_score), 6),
                    "overlap_score": round(float(overlap_score), 6),
                }
            )

        ranked_items.sort(key=lambda item: (item["score"], item["quality_score"], item["base_score"]), reverse=True)
        return self._dedupe_ranked_payloads(ranked_items, limit=limit)

    def _base_rank_points(self, query: str, points: list[Any], *, limit: int) -> list[dict[str, Any]]:
        if not points:
            return []

        candidate_limit = max(limit, settings.RETRIEVAL_RERANK_CANDIDATES)
        trimmed_points = points[:candidate_limit]
        base_scores = [float(point.score or 0.0) for point in trimmed_points]
        payloads = [point.payload for point in trimmed_points]
        quality_scores = [safe_float(payload.get("quality_score"), 0.0) for payload in payloads]
        overlap_scores = [self._name_overlap_score(query, payload) for payload in payloads]
        planner_weights = [safe_float(payload.get("planner_rank_weight"), 0.0) for payload in payloads]

        normalized_base = self._normalize_scores(base_scores)

        ranked_items = []
        for point, base_score, quality_score, overlap_score, planner_weight in zip(
            trimmed_points,
            normalized_base,
            quality_scores,
            overlap_scores,
            planner_weights,
        ):
            final_score = 0.58 * base_score + 0.18 * quality_score + 0.14 * overlap_score + 0.10 * planner_weight
            ranked_items.append(
                {
                    "payload": point.payload,
                    "score": round(final_score, 6),
                    "base_score": round(float(point.score or 0.0), 6),
                    "rerank_score": 0.0,
                    "quality_score": round(float(quality_score), 6),
                    "overlap_score": round(float(overlap_score), 6),
                }
            )

        ranked_items.sort(key=lambda item: (item["score"], item["quality_score"], item["base_score"]), reverse=True)
        return self._dedupe_ranked_payloads(ranked_items, limit=limit)

    def _dedupe_ranked_payloads(self, ranked_items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen_entity_ids: set[str] = set()
        seen_names: set[str] = set()
        for item in ranked_items:
            payload = item["payload"]
            entity_id = payload.get("entity_id")
            normalized_name = ascii_normalize(payload.get("name"))
            if entity_id and entity_id in seen_entity_ids:
                continue
            if normalized_name and normalized_name in seen_names:
                continue
            if entity_id:
                seen_entity_ids.add(entity_id)
            if normalized_name:
                seen_names.add(normalized_name)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    def _rerank_foods(
        self,
        query: str,
        foods: list[dict[str, Any]],
        *,
        limit: int,
        rerank_context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        if not foods:
            return []

        candidate_limit = max(limit, settings.RETRIEVAL_RERANK_CANDIDATES)
        trimmed_foods = foods[:candidate_limit]
        base_scores = [safe_float(food.get("retrieval_score"), 0.0) for food in trimmed_foods]
        documents = [food.get("hybrid_text") or food.get("dense_text") or food.get("content") or food.get("name") or "" for food in trimmed_foods]
        rerank_scores = self.embedder.rerank_documents(query, documents) if settings.RETRIEVAL_ENABLE_RERANK else [0.0 for _ in documents]
        quality_scores = [safe_float(food.get("quality_score"), 0.0) for food in trimmed_foods]
        overlap_scores = [self._name_overlap_score(query, food) for food in trimmed_foods]
        planner_weights = [safe_float(food.get("planner_rank_weight"), 0.0) for food in trimmed_foods]
        role_scores = [self._role_alignment_score(food, (rerank_context or {}).get("expected_role_tags") or []) for food in trimmed_foods]
        anchor_scores = [self._phrase_alignment_score(food, (rerank_context or {}).get("anchor_terms") or []) for food in trimmed_foods]
        must_include_scores = [self._must_include_score(food, (rerank_context or {}).get("must_include") or []) for food in trimmed_foods]

        normalized_base = self._normalize_scores(base_scores)
        normalized_rerank = self._normalize_scores(rerank_scores)

        rescored: list[dict[str, Any]] = []
        for food, base_score, rerank_score, quality_score, overlap_score, planner_weight, role_score, anchor_score, must_include_score in zip(
            trimmed_foods,
            normalized_base,
            normalized_rerank,
            quality_scores,
            overlap_scores,
            planner_weights,
            role_scores,
            anchor_scores,
            must_include_scores,
        ):
            generic_penalty = self._generic_penalty(food, rerank_context, anchor_match_score=anchor_score, must_include_score=must_include_score)
            final_score = (
                0.20 * base_score
                + 0.15 * rerank_score
                + 0.10 * quality_score
                + 0.08 * overlap_score
                + 0.05 * planner_weight
                + 0.20 * role_score
                + 0.08 * anchor_score
                + 0.25 * must_include_score
                - 0.15 * generic_penalty
            )
            rescored_food = dict(food)
            rescored_food["retrieval_score"] = round(min(max(final_score, 0.0), 1.0), 6)
            rescored.append(rescored_food)

        rescored.sort(key=lambda item: (safe_float(item.get("retrieval_score"), 0.0), safe_float(item.get("quality_score"), 0.0)), reverse=True)
        return rescored[:limit]
