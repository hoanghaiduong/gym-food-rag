from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from app.core.config import settings

from .normalize import ascii_normalize
from .payloads import payload_to_food


class RepositoryMixin:
    def _coerce_query_entries(self, queries: list[Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for index, raw_query in enumerate(queries):
            if isinstance(raw_query, dict):
                query_text = str(raw_query.get("query") or "").strip()
                channel = str(raw_query.get("channel") or f"channel_{index + 1}").strip()
                expected_role_tags = [
                    str(tag).strip()
                    for tag in (raw_query.get("expected_role_tags") or [])
                    if str(tag).strip()
                ]
                query_purpose = str(raw_query.get("query_purpose") or "").strip()
            else:
                query_text = str(raw_query or "").strip()
                channel = f"channel_{index + 1}"
                expected_role_tags = []
                query_purpose = ""
            if not query_text:
                continue
            entries.append(
                {
                    "query": query_text,
                    "channel": channel or f"channel_{index + 1}",
                    "expected_role_tags": expected_role_tags,
                    "query_purpose": query_purpose or f"channel_{index + 1}",
                }
            )
        return entries

    def _query_points(
        self,
        query: str,
        limit: int,
        dietary_preference: Optional[str],
        allergy_tags: Iterable[str],
        entity_types: Optional[Iterable[str]],
        expected_role_tags: Optional[Iterable[str]] = None,  # New param for hard role filtering
        *,
        rerank: bool = True,
    ) -> list[dict[str, Any]]:
        hybrid_query = self.embedder.encode_hybrid(query)
        # Pass expected roles to enable hard must filter on meal_role_tags -> higher precision & recall
        query_filter = self._build_filter(
            dietary_preference, allergy_tags, entity_types, expected_role_tags
        )
        search_limit = max(limit * 5, limit + 20)
        prefetch_limit = max(search_limit * 3, 30)

        result = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                self.models.Prefetch(query=hybrid_query.dense, using="dense", limit=prefetch_limit),
                self.models.Prefetch(query=hybrid_query.sparse.as_object(), using="sparse", limit=prefetch_limit),
            ],
            query=self.models.FusionQuery(fusion=self.models.Fusion.RRF),
            query_filter=query_filter,
            limit=search_limit,
        )
        if rerank and settings.RETRIEVAL_ENABLE_RERANK:
            return self._rerank_points(query, result.points, limit=limit)
        return self._base_rank_points(query, result.points, limit=limit)

    def retrieve_candidates(
        self,
        queries: list[Any],
        *,
        limit: int,
        dietary_preference: Optional[str] = None,
        allergy_tags: Optional[list[str]] = None,
        excluded_foods: Optional[list[str]] = None,
        entity_types: Optional[list[str]] = None,
        dietary_filter: bool = True,
        rerank_context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        allergy_tags = allergy_tags or []
        excluded_foods = excluded_foods or []
        normalized_exclusions = [ascii_normalize(item) for item in excluded_foods if item]
        query_entries = self._coerce_query_entries(queries)
        if not query_entries:
            return []

        merged: dict[str, dict[str, Any]] = {}
        for entry in query_entries:
            query = entry["query"]
            channel = entry["channel"]
            expected_role_tags = list(entry.get("expected_role_tags") or [])
            query_purpose = str(entry.get("query_purpose") or channel)
            result = self._query_points(
                query=query,
                limit=max(8, min(limit, 24)),
                dietary_preference=dietary_preference if dietary_filter else None,
                allergy_tags=allergy_tags,
                entity_types=entity_types,
                expected_role_tags=expected_role_tags,
                rerank=False,
            )
            for ranked_point in result:
                food = payload_to_food(ranked_point["payload"], ranked_point["score"])
                entity_id = food["entity_id"]
                if not entity_id:
                    continue
                normalized_name = ascii_normalize(food.get("name"))
                if any(item and item in normalized_name for item in normalized_exclusions):
                    continue
                current = merged.get(entity_id)
                food["source_channels"] = [channel]
                food["source_queries"] = [query]
                food["source_query_purposes"] = [query_purpose]
                food["source_expected_role_tags"] = expected_role_tags
                if current is None:
                    merged[entity_id] = food
                    continue
                existing_channels = set(current.get("source_channels") or [])
                existing_queries = list(current.get("source_queries") or [])
                existing_purposes = list(current.get("source_query_purposes") or [])
                existing_expected_roles = set(current.get("source_expected_role_tags") or [])
                if channel not in existing_channels:
                    existing_queries.append(query)
                    existing_purposes.append(query_purpose)
                current["source_channels"] = sorted(existing_channels | {channel})
                current["source_queries"] = existing_queries[:6]
                current["source_query_purposes"] = existing_purposes[:6]
                current["source_expected_role_tags"] = sorted(existing_expected_roles | set(expected_role_tags))
                if (food.get("retrieval_score") or 0) > (current.get("retrieval_score") or 0):
                    merged[entity_id] = {
                        **current,
                        **food,
                        "source_channels": current["source_channels"],
                        "source_queries": current["source_queries"],
                        "source_query_purposes": current["source_query_purposes"],
                        "source_expected_role_tags": current["source_expected_role_tags"],
                    }

        foods = sorted(merged.values(), key=lambda item: item.get("retrieval_score") or 0.0, reverse=True)
        if foods:
            rerank_query_parts = [entry["query"] for entry in query_entries[:2]]
            rerank_query = " ".join(rerank_query_parts) if len(rerank_query_parts) > 1 else query_entries[0]["query"]
            rerank_limit = max(limit * settings.RETRIEVAL_OVERFETCH_MULTIPLIER, settings.RETRIEVAL_RERANK_CANDIDATES)
            return self._rerank_foods(rerank_query, foods[:rerank_limit], limit=limit, rerank_context=rerank_context)

        fallback_result = self._query_points(
            query=query_entries[0]["query"],
            limit=limit,
            dietary_preference=None,
            allergy_tags=[],
            entity_types=entity_types,
            expected_role_tags=query_entries[0].get("expected_role_tags") or None,
            rerank=True,
        )
        return [payload_to_food(point["payload"], point["score"]) for point in fallback_result][:limit]

    def resolve_food_reference(
        self,
        *,
        entity_id: Optional[str],
        food_name: Optional[str],
        candidate_map: dict[str, dict[str, Any]],
        allow_global_lookup: bool = True,
        allow_blocked_lookup: bool = False,
    ) -> Optional[dict[str, Any]]:
        if entity_id and entity_id in candidate_map:
            return candidate_map[entity_id]

        normalized_name = ascii_normalize(food_name)
        if normalized_name:
            for candidate in candidate_map.values():
                candidate_name = ascii_normalize(candidate.get("name"))
                candidate_name_en = ascii_normalize(candidate.get("name_en"))
                candidate_aliases = [ascii_normalize(alias) for alias in candidate.get("aliases") or []]
                if normalized_name in {candidate_name, candidate_name_en, *candidate_aliases}:
                    return candidate
                if candidate_name and (normalized_name in candidate_name or candidate_name in normalized_name):
                    return candidate
                if candidate_name_en and (normalized_name in candidate_name_en or candidate_name_en in normalized_name):
                    return candidate

        self._ensure_local_index()
        assert self._records_by_entity_id is not None
        assert self._records_by_name is not None
        assert self._all_records_by_entity_id is not None
        assert self._all_records_by_name is not None

        if entity_id and entity_id in self._records_by_entity_id:
            return payload_to_food(self._records_by_entity_id[entity_id])
        if allow_blocked_lookup and entity_id and entity_id in self._all_records_by_entity_id:
            return payload_to_food(self._all_records_by_entity_id[entity_id])

        if normalized_name in self._records_by_name:
            return payload_to_food(self._records_by_name[normalized_name])
        if allow_blocked_lookup and normalized_name in self._all_records_by_name:
            return payload_to_food(self._all_records_by_name[normalized_name])

        if not allow_global_lookup or not normalized_name:
            return None

        payload_source = (
            self._all_records_by_entity_id.values()
            if allow_blocked_lookup
            else self._records_by_entity_id.values()
        )
        for payload in payload_source:
            name_key = ascii_normalize(payload.get("name"))
            if normalized_name and (normalized_name in name_key or name_key in normalized_name):
                return payload_to_food(payload)

        search_result = self._query_points(
            query=food_name or "",
            limit=1,
            dietary_preference=None,
            allergy_tags=[],
            entity_types=None,
        )
        if search_result:
            return payload_to_food(search_result[0]["payload"], search_result[0]["score"])
        return None

    def _family_lookup_keys(self, food: dict[str, Any]) -> list[str]:
        keys: list[str] = []
        for raw_value in [
            food.get("meal_family_key"),
            food.get("canonical_name_key"),
            food.get("name"),
            food.get("safe_display_name"),
        ]:
            normalized = ascii_normalize(raw_value)
            if not normalized or normalized in keys:
                continue
            keys.append(normalized)
        return keys

    def _macro_similarity_score(self, source: dict[str, Any], candidate: dict[str, Any]) -> float:
        distance = 0.0
        for field_name in ["energy_kcal", "protein_g", "carbs_g", "fat_g"]:
            source_value = float(source.get(field_name) or 0.0)
            candidate_value = float(candidate.get(field_name) or 0.0)
            scale = max(abs(source_value), 1.0)
            distance += abs(candidate_value - source_value) / scale
        return 1.0 / (1.0 + distance)

    def _token_overlap_score(self, source: dict[str, Any], candidate: dict[str, Any]) -> float:
        source_text = " ".join(self._family_lookup_keys(source))
        candidate_text = " ".join(self._family_lookup_keys(candidate))
        source_tokens = {token for token in re.sub(r"[^a-z0-9]+", " ", source_text).split() if token}
        candidate_tokens = {token for token in re.sub(r"[^a-z0-9]+", " ", candidate_text).split() if token}
        if not source_tokens or not candidate_tokens:
            return 0.0
        return len(source_tokens & candidate_tokens) / float(len(source_tokens | candidate_tokens))

    def find_safe_sibling(
        self,
        *,
        food_ref: dict[str, Any] | None = None,
        entity_id: Optional[str] = None,
        food_name: Optional[str] = None,
        candidate_map: Optional[dict[str, dict[str, Any]]] = None,
    ) -> Optional[dict[str, Any]]:
        source = food_ref or self.resolve_food_reference(
            entity_id=entity_id,
            food_name=food_name,
            candidate_map=candidate_map or {},
            allow_global_lookup=True,
            allow_blocked_lookup=True,
        )
        if not source:
            return None

        self._ensure_local_index()
        assert self._records_by_family_key is not None

        family_keys = self._family_lookup_keys(source)
        candidate_payloads: list[dict[str, Any]] = []
        seen_entity_ids: set[str] = set()

        for key in family_keys:
            for payload in self._records_by_family_key.get(key, []):
                entity_id_value = payload.get("entity_id")
                if not entity_id_value or entity_id_value == source.get("entity_id") or entity_id_value in seen_entity_ids:
                    continue
                seen_entity_ids.add(entity_id_value)
                candidate_payloads.append(payload)

        for query in family_keys[:2]:
            for candidate in self.search_local_candidates(
                query,
                limit=12,
                dietary_preference=None,
                allergy_tags=[],
                excluded_foods=[],
                entity_types=[source.get("entity_type")] if source.get("entity_type") else None,
            ):
                entity_id_value = candidate.get("entity_id")
                if not entity_id_value or entity_id_value == source.get("entity_id") or entity_id_value in seen_entity_ids:
                    continue
                seen_entity_ids.add(entity_id_value)
                candidate_payloads.append(candidate)

        safe_candidates = [
            payload_to_food(candidate) if "dense_text" in candidate else candidate
            for candidate in candidate_payloads
            if candidate.get("final_output_allowed") is not False
            and candidate.get("production_retrieval_enabled") is not False
        ]
        if not safe_candidates:
            return None

        source_family_key = ascii_normalize(source.get("meal_family_key") or source.get("canonical_name_key"))
        ranked = sorted(
            safe_candidates,
            key=lambda item: (
                ascii_normalize(item.get("meal_family_key") or item.get("canonical_name_key")) == source_family_key,
                self._token_overlap_score(source, item),
                self._macro_similarity_score(source, item),
                float(item.get("planner_rank_weight") or 0.0),
                float(item.get("retrieval_score") or 0.0),
                float(item.get("quality_score") or 0.0),
            ),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def format_candidates_for_prompt(self, candidates: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for item in candidates:
            lines.append(
                (
                    f"- entity_id={item['entity_id']} | name={item['name']} | "
                    f"safe_name={item.get('safe_display_name') or item['name']} | "
                    f"final_output_allowed={bool(item.get('final_output_allowed', True))} | "
                    f"type={item.get('entity_type') or 'food'} | "
                    f"kcal={item['energy_kcal']:.1f} | protein_g={item['protein_g']:.1f} | "
                    f"carbs_g={item['carbs_g']:.1f} | fat_g={item['fat_g']:.1f} | "
                    f"group={item.get('group_name') or 'Unknown'} | "
                    f"diet_tags={','.join(item.get('diet_tags') or []) or 'none'} | "
                    f"allergen_tags={','.join(item.get('allergen_tags') or []) or 'none'}"
                )
            )
        return "\n".join(lines)
