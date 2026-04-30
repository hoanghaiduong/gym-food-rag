from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.paths import PROCESSED_DATA_DIR

from .diet_compatibility import matches_dietary_preference
from .exclusion_matching import payload_matches_exclusion
from .hint_matching import candidate_matches_runtime_hint
from .normalize import ascii_normalize, safe_float
from .payloads import build_vector_payload, is_qdrant_ready_record, payload_to_food


QDRANT_READY_JSONL_PATH = PROCESSED_DATA_DIR / "nutrition_kb_qdrant.jsonl"
MASTER_JSONL_PATH = PROCESSED_DATA_DIR / "nutrition_kb_master.jsonl"
FOODS_JSONL_PATH = PROCESSED_DATA_DIR / "foods_full_profile.jsonl"


def default_runtime_jsonl_path() -> Path:
    if QDRANT_READY_JSONL_PATH.exists():
        return QDRANT_READY_JSONL_PATH
    if MASTER_JSONL_PATH.exists():
        return MASTER_JSONL_PATH
    return FOODS_JSONL_PATH


class LocalIndexMixin:
    def _ensure_local_index(self) -> None:
        if (
            self._records_by_entity_id is not None
            and self._records_by_name is not None
            and self._records_by_family_key is not None
            and self._all_records_by_entity_id is not None
            and self._all_records_by_name is not None
            and self._all_records_by_family_key is not None
        ):
            return

        records_by_entity_id: dict[str, dict[str, Any]] = {}
        records_by_name: dict[str, dict[str, Any]] = {}
        records_by_family_key: dict[str, list[dict[str, Any]]] = {}
        all_records_by_entity_id: dict[str, dict[str, Any]] = {}
        all_records_by_name: dict[str, dict[str, Any]] = {}
        all_records_by_family_key: dict[str, list[dict[str, Any]]] = {}

        with self.jsonl_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                record = json.loads(raw_line)
                payload = record if is_qdrant_ready_record(record) else build_vector_payload(record)
                entity_id = payload["entity_id"]
                if not entity_id:
                    continue
                all_records_by_entity_id[entity_id] = payload
                all_records_by_name[ascii_normalize(payload.get("name"))] = payload
                if payload.get("name_en"):
                    all_records_by_name.setdefault(ascii_normalize(payload["name_en"]), payload)
                family_key = ascii_normalize(payload.get("meal_family_key") or payload.get("canonical_name_key"))
                if family_key:
                    all_records_by_family_key.setdefault(family_key, []).append(payload)
                if payload.get("qdrant_ingest_eligible") is False:
                    continue
                if payload.get("production_retrieval_enabled") is False:
                    continue
                records_by_entity_id[entity_id] = payload
                records_by_name[ascii_normalize(payload.get("name"))] = payload
                if payload.get("name_en"):
                    records_by_name.setdefault(ascii_normalize(payload["name_en"]), payload)
                if family_key:
                    records_by_family_key.setdefault(family_key, []).append(payload)

        self._records_by_entity_id = records_by_entity_id
        self._records_by_name = records_by_name
        self._records_by_family_key = records_by_family_key
        self._all_records_by_entity_id = all_records_by_entity_id
        self._all_records_by_name = all_records_by_name
        self._all_records_by_family_key = all_records_by_family_key

    def _matches_preference_locally(self, dietary_preference: Optional[str], payload: dict[str, Any]) -> bool:
        return matches_dietary_preference(
            dietary_preference,
            payload.get("diet_tags") or [],
            payload,
        )

    def _payload_matches_filters(
        self,
        payload: dict[str, Any],
        *,
        dietary_preference: Optional[str],
        allergy_tags: Iterable[str],
        excluded_foods: Optional[Iterable[str]],
        entity_types: Optional[Iterable[str]],
    ) -> bool:
        if payload.get("retrieval_enabled") is False:
            return False
        if payload.get("qdrant_ingest_eligible") is False:
            return False
        if payload.get("production_retrieval_enabled") is False:
            return False

        entity_type_values = {item for item in (entity_types or []) if item}
        if entity_type_values and payload.get("entity_type") not in entity_type_values:
            return False

        if not self._matches_preference_locally(dietary_preference, payload):
            return False

        allergy_values = {item for item in (allergy_tags or []) if item}
        if allergy_values.intersection(set(payload.get("allergen_tags") or [])):
            return False

        normalized_exclusions = [ascii_normalize(item) for item in (excluded_foods or []) if item]
        if any(payload_matches_exclusion(payload, item) for item in normalized_exclusions):
            return False

        return True

    def list_local_candidates(
        self,
        *,
        limit: Optional[int] = None,
        dietary_preference: Optional[str] = None,
        allergy_tags: Optional[list[str]] = None,
        excluded_foods: Optional[list[str]] = None,
        entity_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        self._ensure_local_index()
        assert self._records_by_entity_id is not None

        candidates: list[dict[str, Any]] = []
        for payload in self._records_by_entity_id.values():
            if not self._payload_matches_filters(
                payload,
                dietary_preference=dietary_preference,
                allergy_tags=allergy_tags or [],
                excluded_foods=excluded_foods or [],
                entity_types=entity_types,
            ):
                continue
            candidates.append(payload_to_food(payload))

        candidates.sort(
            key=lambda item: (
                safe_float(item.get("planner_rank_weight"), 0.0),
                safe_float(item.get("quality_score"), 0.0),
                safe_float(item.get("protein_g"), 0.0),
                safe_float(item.get("energy_kcal"), 0.0),
            ),
            reverse=True,
        )
        if limit is None:
            return candidates
        return candidates[:limit]

    def search_local_candidates(
        self,
        query: str,
        *,
        limit: int = 8,
        dietary_preference: Optional[str] = None,
        allergy_tags: Optional[list[str]] = None,
        excluded_foods: Optional[list[str]] = None,
        entity_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        normalized_query = ascii_normalize(query)
        if not normalized_query:
            return []

        self._ensure_local_index()
        assert self._records_by_entity_id is not None

        scored: list[tuple[float, dict[str, Any]]] = []
        for payload in self._records_by_entity_id.values():
            if not self._payload_matches_filters(
                payload,
                dietary_preference=dietary_preference,
                allergy_tags=allergy_tags or [],
                excluded_foods=excluded_foods or [],
                entity_types=entity_types,
            ):
                continue

            semantic_hint_match = candidate_matches_runtime_hint(payload, normalized_query)
            if semantic_hint_match is False:
                continue

            overlap = self._name_overlap_score(normalized_query, payload)
            anchor_overlap = self._phrase_alignment_score(payload, [normalized_query])
            candidate_name = ascii_normalize(payload.get("name"))
            anchor_text = ascii_normalize(self._payload_anchor_text(payload))
            exact_match = 1.0 if candidate_name == normalized_query else 0.0
            contains_match = 1.0 if normalized_query in candidate_name or candidate_name in normalized_query else 0.0
            anchor_contains_match = 1.0 if normalized_query in anchor_text else 0.0
            semantic_bonus = 1.0 if semantic_hint_match is True else 0.0
            role_bonus = 0.0
            if normalized_query in {"rau", "rau xanh", "rau luoc", "trai cay", "hoa qua"}:
                role_bonus = 1.0 if "produce_support" in (payload.get("meal_role_tags") or []) else 0.0
            elif normalized_query in {"gao", "com", "yen mach", "khoai"}:
                role_bonus = 1.0 if "carb_anchor" in (payload.get("meal_role_tags") or []) else 0.0
            elif normalized_query in {"ca", "trung", "thit ga", "dau hu", "dau nanh"}:
                role_bonus = 1.0 if "protein_anchor" in (payload.get("meal_role_tags") or []) else 0.0
            quality = safe_float(payload.get("quality_score"), 0.0)
            carbs = safe_float(payload.get("carbs_g"), 0.0)
            protein = safe_float(payload.get("protein_g"), 0.0)
            fat = safe_float(payload.get("fat_g"), 0.0)
            staple_bonus = 0.0
            mixed_meal_penalty = 0.0
            if normalized_query in {"gao", "com", "gao lut"} and semantic_hint_match is True:
                staple_bonus += 0.30 * min(carbs / 60.0, 1.2)
                if fat <= 6:
                    staple_bonus += 0.35
                if protein <= 10:
                    staple_bonus += 0.15
                if fat >= 15:
                    mixed_meal_penalty += 0.45
                if protein >= 20 and fat >= 12:
                    mixed_meal_penalty += 0.20
            score = (
                0.35 * overlap
                + 0.20 * anchor_overlap
                + 0.15 * exact_match
                + 0.10 * contains_match
                + 0.10 * anchor_contains_match
                + 0.05 * role_bonus
                + 0.20 * semantic_bonus
                + staple_bonus
                + 0.10 * quality
                - mixed_meal_penalty
            )
            if score <= 0:
                continue
            scored.append((score, payload))

        scored.sort(
            key=lambda item: (
                item[0],
                safe_float(item[1].get("quality_score"), 0.0),
                safe_float(item[1].get("protein_g"), 0.0),
                safe_float(item[1].get("energy_kcal"), 0.0),
            ),
            reverse=True,
        )

        deduped: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        seen_entity_ids: set[str] = set()
        for _, payload in scored:
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
            deduped.append(payload_to_food(payload))
            if len(deduped) >= limit:
                break
        return deduped
