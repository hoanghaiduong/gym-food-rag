from __future__ import annotations

from typing import Any, Optional

from app.services.nutrition_record_policy import enrich_meal_ready_record

from .normalize import format_metric, safe_float, sanitize_json_payload
from .tags import derive_allergen_tags, derive_diet_tags


def build_dense_text(record: dict[str, Any], allergen_tags: list[str], diet_tags: list[str]) -> str:
    entity_type = record.get("entity_type", "food")
    entity_label = "Mon an" if entity_type == "dish" else "Thuc pham"
    names = [record.get("name"), record.get("name_en")]
    aliases = ", ".join(alias for alias in (record.get("aliases") or []) if alias)
    nutrient_bits = []
    for field_name, label, unit in [
        ("energy_kcal", "Energy", "kcal"),
        ("protein_g", "Protein", "g"),
        ("carbs_g", "Carbohydrate", "g"),
        ("fat_g", "Fat", "g"),
        ("fiber_g", "Fiber", "g"),
        ("vitamin_c_mg", "Vitamin C", "mg"),
        ("calcium_mg", "Calcium", "mg"),
        ("iron_mg", "Iron", "mg"),
        ("zinc_mg", "Zinc", "mg"),
        ("sodium_mg", "Sodium", "mg"),
        ("potassium_mg", "Potassium", "mg"),
    ]:
        value = format_metric(record.get(field_name))
        if value is not None:
            nutrient_bits.append(f"{label} {value}{unit}")

    taxonomy_parts = [record.get("taxonomy_level_1"), record.get("taxonomy_level_2"), record.get("granularity")]
    portion_basis = record.get("portion_basis") or ("per_serving" if entity_type == "dish" else "per_100g")
    portion_g = format_metric(record.get("portion_g"))
    portion_text = portion_basis if portion_g is None else f"{portion_basis} {portion_g}g"

    clauses = [
        f"{entity_label}: {' / '.join(str(name) for name in names if name)}.",
        f"Nhom: {record.get('group_name') or record.get('group') or 'unknown'}.",
        f"Taxonomy: {' > '.join(str(item) for item in taxonomy_parts if item)}.",
        f"Portion basis: {portion_text}.",
    ]
    if aliases:
        clauses.append(f"Aliases: {aliases}.")
    if nutrient_bits:
        clauses.append("Nutrients: " + ", ".join(nutrient_bits) + ".")
    if record.get("meal_suggestion"):
        clauses.append(f"Meal suggestion: {record.get('meal_suggestion')}.")
    if record.get("meal_role_tags"):
        clauses.append(f"Meal roles: {', '.join(record.get('meal_role_tags') or [])}.")
    if record.get("meal_readiness_tier"):
        clauses.append(
            f"Meal readiness: {record.get('meal_readiness_tier')} "
            f"(score {format_metric(record.get('meal_readiness_score')) or 'unknown'})."
        )
    if record.get("consumption_state"):
        clauses.append(f"Consumption state: {record.get('consumption_state')}.")
    if record.get("final_output_allowed") is not None:
        clauses.append(
            "Final output allowed: "
            + ("yes." if record.get("final_output_allowed") else "no.")
        )
    if record.get("unsafe_output_reason"):
        clauses.append(f"Unsafe output reason: {record.get('unsafe_output_reason')}.")
    if record.get("safe_display_name"):
        clauses.append(f"Safe display name: {record.get('safe_display_name')}.")
    if record.get("ingredient_hints"):
        clauses.append(f"Ingredient hints: {', '.join(record.get('ingredient_hints') or [])}.")
    if diet_tags:
        clauses.append(f"Diet tags: {', '.join(diet_tags)}.")
    if allergen_tags:
        clauses.append(f"Allergen tags: {', '.join(allergen_tags)}.")
    if record.get("source_name") or record.get("provenance"):
        clauses.append(f"Source: {record.get('source_name') or record.get('provenance')}.")
    return " ".join(clauses)


def build_sparse_text(record: dict[str, Any], allergen_tags: list[str], diet_tags: list[str]) -> str:
    token_parts = [
        record.get("entity_type"),
        record.get("granularity"),
        record.get("schema_version"),
        record.get("name"),
        record.get("name_en"),
        *(record.get("aliases") or []),
        record.get("group_name"),
        record.get("group"),
        record.get("group_slug"),
        record.get("category_id"),
        record.get("category_slug"),
        record.get("category_name_en"),
        record.get("taxonomy_level_1"),
        record.get("taxonomy_level_2"),
        record.get("taxonomy_version"),
        record.get("canonical_name_key"),
        record.get("meal_family_key"),
        record.get("preparation_style"),
        record.get("meal_suggestion"),
        record.get("meal_readiness_tier"),
        record.get("consumption_state"),
        record.get("final_output_allowed"),
        record.get("unsafe_output_reason"),
        record.get("safe_display_name"),
        *(record.get("meal_role_tags") or []),
        *(record.get("ingredient_hints") or []),
        record.get("source_code"),
        record.get("source_name"),
        record.get("portion_basis"),
        record.get("portion_g_source"),
        record.get("serving_size_confidence"),
        *(diet_tags or []),
        *(allergen_tags or []),
    ]
    nutrient_tokens = []
    for field_name, aliases in [
        ("energy_kcal", ["energy", "kcal", "calories"]),
        ("protein_g", ["protein", "dam"]),
        ("carbs_g", ["carb", "carbohydrate", "glucid"]),
        ("fat_g", ["fat", "lipid", "beo"]),
        ("fiber_g", ["fiber", "xÆ¡"]),
        ("vitamin_c_mg", ["vitamin_c", "vitamin c"]),
        ("calcium_mg", ["calcium", "ca", "canxi"]),
        ("iron_mg", ["iron", "fe", "sat"]),
        ("zinc_mg", ["zinc", "zn", "kem"]),
        ("sodium_mg", ["sodium", "na", "natri"]),
        ("potassium_mg", ["potassium", "k", "kali"]),
    ]:
        value = format_metric(record.get(field_name))
        if value is None:
            continue
        for alias in aliases:
            nutrient_tokens.append(f"{alias} {value}")
            nutrient_tokens.append(f"{alias}:{value}")
    return " | ".join(str(token) for token in token_parts + nutrient_tokens if token)


def build_canonical_content(record: dict[str, Any], allergen_tags: list[str], diet_tags: list[str]) -> str:
    def nutrient_value(field_name: str) -> str:
        value = safe_float(record.get(field_name), None)
        return "unknown" if value is None else str(value)

    nutrient_clauses = []
    for field_name, label in [
        ("fiber_g", "Fiber"),
        ("vitamin_c_mg", "Vitamin C"),
        ("calcium_mg", "Calcium"),
        ("iron_mg", "Iron"),
        ("zinc_mg", "Zinc"),
        ("sodium_mg", "Sodium"),
        ("potassium_mg", "Potassium"),
        ("magnesium_mg", "Magnesium"),
        ("phosphorus_mg", "Phosphorus"),
    ]:
        value = safe_float(record.get(field_name), None)
        if value is None:
            continue
        unit = "g" if field_name.endswith("_g") else "mg"
        nutrient_clauses.append(f"{label} {value}{unit}")

    entity_label = "Mon an" if str(record.get("entity_type")) == "dish" else "Thuc pham"
    portion_basis = record.get("portion_basis") or "per_100g"
    portion_g = safe_float(record.get("portion_g"), None)
    if portion_basis == "per_serving":
        basis_text = "kcal/serving" if portion_g is None else f"kcal/{portion_g}g serving"
    else:
        basis_text = "kcal/100g" if portion_g is None else f"kcal/{portion_g}g"
    base_content = (
        f"{entity_label}: {record.get('name')}. "
        f"Nhom: {record.get('group_name') or record.get('group')}. "
        f"Nang luong {nutrient_value('energy_kcal')} {basis_text}. "
        f"Protein {nutrient_value('protein_g')}g, "
        f"Carb {nutrient_value('carbs_g')}g, "
        f"Fat {nutrient_value('fat_g')}g."
    )
    if nutrient_clauses:
        base_content += " " + ", ".join(nutrient_clauses) + "."
    if record.get("meal_role_tags"):
        base_content += f" Meal roles: {', '.join(record.get('meal_role_tags') or [])}."
    if record.get("consumption_state"):
        base_content += f" Consumption state: {record.get('consumption_state')}."
    if record.get("final_output_allowed") is not None:
        base_content += (
            " Final output allowed: yes."
            if record.get("final_output_allowed")
            else " Final output allowed: no."
        )
    if record.get("unsafe_output_reason"):
        base_content += f" Unsafe output reason: {record.get('unsafe_output_reason')}."
    if record.get("safe_display_name"):
        base_content += f" Safe display name: {record.get('safe_display_name')}."
    if record.get("ingredient_hints"):
        base_content += f" Ingredient hints: {', '.join(record.get('ingredient_hints') or [])}."
    tag_text = f" Diet tags: {', '.join(diet_tags)}." if diet_tags else ""
    allergen_text = f" Allergen tags: {', '.join(allergen_tags)}." if allergen_tags else ""
    return f"{base_content}{tag_text}{allergen_text}".strip()


def build_hybrid_text(dense_text: str, sparse_text: str) -> str:
    normalized_dense = (dense_text or "").strip()
    normalized_sparse = (sparse_text or "").strip()
    if not normalized_sparse or normalized_sparse == normalized_dense:
        return normalized_dense
    return f"{normalized_dense}\nKeywords: {normalized_sparse}"


def build_vector_payload(record: dict[str, Any]) -> dict[str, Any]:
    record = enrich_meal_ready_record(record)
    allergen_tags = derive_allergen_tags(record)
    diet_tags = derive_diet_tags(record, allergen_tags)
    entity_type = record.get("entity_type", "food")
    portion_basis = record.get("portion_basis", "per_100g" if entity_type == "food" else "per_serving")
    portion_default = 100.0 if portion_basis == "per_100g" else None
    qdrant_exclusion_reasons = list(record.get("qdrant_exclusion_reasons") or [])
    production_block_reasons = list(record.get("production_block_reasons") or [])
    final_output_allowed = bool(record.get("final_output_allowed"))
    production_retrieval_enabled = bool(record.get("production_retrieval_enabled", final_output_allowed))
    retrieval_enabled = bool(record.get("retrieval_enabled", True))
    qdrant_ingest_eligible = bool(record.get("qdrant_ingest_eligible", True))
    if not final_output_allowed or not production_retrieval_enabled or record.get("meal_readiness_tier") == "blocked":
        retrieval_enabled = False
        qdrant_ingest_eligible = False
        production_retrieval_enabled = False
        unsafe_reason = str(record.get("unsafe_output_reason") or "").strip()
        if unsafe_reason and unsafe_reason not in qdrant_exclusion_reasons:
            qdrant_exclusion_reasons.append(unsafe_reason)
        if "unsafe_final_output" not in qdrant_exclusion_reasons:
            qdrant_exclusion_reasons.append("unsafe_final_output")
        if unsafe_reason and unsafe_reason not in production_block_reasons:
            production_block_reasons.append(unsafe_reason)

    payload = {
        "entity_id": record.get("entity_id"),
        "entity_type": entity_type,
        "granularity": record.get("granularity", "ingredient" if entity_type == "food" else "dish"),
        "schema_version": record.get("schema_version", "v1"),
        "food_id": record.get("food_id"),
        "dish_id": record.get("dish_id"),
        "name": record.get("name"),
        "name_en": record.get("name_en"),
        "aliases": record.get("aliases") or [],
        "group_name": record.get("group_name") or record.get("group"),
        "group": record.get("group") or record.get("group_name"),
        "group_slug": record.get("group_slug"),
        "category_id": record.get("category_id"),
        "category_slug": record.get("category_slug"),
        "category_name_en": record.get("category_name_en"),
        "taxonomy_level_1": record.get("taxonomy_level_1"),
        "taxonomy_level_2": record.get("taxonomy_level_2"),
        "taxonomy_version": record.get("taxonomy_version"),
        "canonical_name_key": record.get("canonical_name_key"),
        "meal_family_key": record.get("meal_family_key"),
        "exact_dedup_key": record.get("exact_dedup_key"),
        "family_variant_count": record.get("family_variant_count"),
        "variant_count": record.get("variant_count"),
        "portion_g": safe_float(record.get("portion_g"), portion_default),
        "portion_basis": portion_basis,
        "portion_g_source": record.get("portion_g_source"),
        "serving_size_confidence": record.get("serving_size_confidence"),
        "energy_kcal": safe_float(record.get("energy_kcal")),
        "protein_g": safe_float(record.get("protein_g")),
        "carbs_g": safe_float(record.get("carbs_g")),
        "fat_g": safe_float(record.get("fat_g")),
        "fiber_g": safe_float(record.get("fiber_g"), None),
        "vitamin_c_mg": safe_float(record.get("vitamin_c_mg"), None),
        "calcium_mg": safe_float(record.get("calcium_mg"), None),
        "iron_mg": safe_float(record.get("iron_mg"), None),
        "zinc_mg": safe_float(record.get("zinc_mg"), None),
        "sodium_mg": safe_float(record.get("sodium_mg"), None),
        "potassium_mg": safe_float(record.get("potassium_mg"), None),
        "preparation_style": record.get("preparation_style"),
        "ingredient_components_normalized": record.get("ingredient_components_normalized") or [],
        "ingredient_hints": record.get("ingredient_hints") or [],
        "ingredient_detail_source": record.get("ingredient_detail_source"),
        "meal_suggestion": record.get("meal_suggestion", "General"),
        "image_url": record.get("image_url"),
        "image_local_url": record.get("image_local_url"),
        "image_source_url": record.get("image_source_url"),
        "source_name": record.get("source_name") or record.get("provenance"),
        "provenance": record.get("provenance"),
        "source_url": record.get("source_url"),
        "updated_at": record.get("updated_at"),
        "quality_score": record.get("quality_score"),
        "quality_tier": record.get("quality_tier"),
        "meal_readiness_score": record.get("meal_readiness_score"),
        "meal_readiness_tier": record.get("meal_readiness_tier"),
        "meal_ready": record.get("meal_ready"),
        "consumption_state": record.get("consumption_state"),
        "final_output_allowed": final_output_allowed,
        "unsafe_output_reason": record.get("unsafe_output_reason"),
        "safe_display_name": record.get("safe_display_name") or record.get("name"),
        "meal_role_tags": record.get("meal_role_tags") or [],
        "meal_role_primary": record.get("meal_role_primary"),
        "planner_rank_weight": record.get("planner_rank_weight"),
        "meal_ready_exclusion_codes": record.get("meal_ready_exclusion_codes") or [],
        "kcal_gap_pct": record.get("kcal_gap_pct"),
        "missing_nutrients_count": record.get("missing_nutrients_count"),
        "retrieval_enabled": retrieval_enabled,
        "qdrant_ingest_eligible": qdrant_ingest_eligible,
        "production_retrieval_enabled": production_retrieval_enabled,
        "qc_severity": record.get("qc_severity"),
        "qc_blocking_codes": record.get("qc_blocking_codes") or [],
        "qdrant_exclusion_reasons": qdrant_exclusion_reasons,
        "production_block_reasons": production_block_reasons,
        "detail_source": record.get("detail_source"),
        "detail_endpoint_found": record.get("detail_endpoint_found"),
        "diet_tags": diet_tags,
        "allergen_tags": allergen_tags,
        "content": build_canonical_content(record, allergen_tags, diet_tags),
        "dense_text": build_dense_text(record, allergen_tags, diet_tags),
        "sparse_text": build_sparse_text(record, allergen_tags, diet_tags),
        "hybrid_text_version": "nutrition_hybrid_v1",
    }
    payload["hybrid_text"] = build_hybrid_text(payload["dense_text"], payload["sparse_text"])
    return sanitize_json_payload(payload)


def is_qdrant_ready_record(record: dict[str, Any]) -> bool:
    ready = bool(
        record.get("entity_id")
        and record.get("content")
        and record.get("dense_text")
        and record.get("sparse_text")
        and isinstance(record.get("diet_tags"), list)
        and isinstance(record.get("allergen_tags"), list)
        and bool(record.get("consumption_state"))
        and record.get("final_output_allowed") is not None
        and bool(record.get("safe_display_name"))
    )
    if not ready:
        return False
    if record.get("final_output_allowed") is False and record.get("qdrant_ingest_eligible") is not False:
        return False
    if record.get("production_retrieval_enabled") is False and record.get("retrieval_enabled") is not False:
        return False
    return True


def payload_to_food(payload: dict[str, Any], score: Optional[float] = None) -> dict[str, Any]:
    return {
        "entity_id": payload.get("entity_id"),
        "entity_type": payload.get("entity_type"),
        "granularity": payload.get("granularity"),
        "food_id": payload.get("food_id"),
        "dish_id": payload.get("dish_id"),
        "name": payload.get("name"),
        "name_en": payload.get("name_en"),
        "group_name": payload.get("group_name") or payload.get("group"),
        "group_slug": payload.get("group_slug"),
        "category_id": payload.get("category_id"),
        "category_slug": payload.get("category_slug"),
        "category_name_en": payload.get("category_name_en"),
        "canonical_name_key": payload.get("canonical_name_key"),
        "meal_family_key": payload.get("meal_family_key"),
        "exact_dedup_key": payload.get("exact_dedup_key"),
        "family_variant_count": payload.get("family_variant_count"),
        "taxonomy_level_1": payload.get("taxonomy_level_1"),
        "taxonomy_level_2": payload.get("taxonomy_level_2"),
        "portion_g": safe_float(payload.get("portion_g"), None),
        "portion_basis": payload.get("portion_basis"),
        "portion_g_source": payload.get("portion_g_source"),
        "serving_size_confidence": payload.get("serving_size_confidence"),
        "energy_kcal": safe_float(payload.get("energy_kcal")),
        "protein_g": safe_float(payload.get("protein_g")),
        "carbs_g": safe_float(payload.get("carbs_g")),
        "fat_g": safe_float(payload.get("fat_g")),
        "fiber_g": safe_float(payload.get("fiber_g"), None),
        "vitamin_c_mg": safe_float(payload.get("vitamin_c_mg"), None),
        "calcium_mg": safe_float(payload.get("calcium_mg"), None),
        "iron_mg": safe_float(payload.get("iron_mg"), None),
        "zinc_mg": safe_float(payload.get("zinc_mg"), None),
        "sodium_mg": safe_float(payload.get("sodium_mg"), None),
        "potassium_mg": safe_float(payload.get("potassium_mg"), None),
        "meal_suggestion": payload.get("meal_suggestion"),
        "preparation_style": payload.get("preparation_style"),
        "ingredient_hints": payload.get("ingredient_hints") or [],
        "ingredient_components_normalized": payload.get("ingredient_components_normalized") or [],
        "ingredient_detail_source": payload.get("ingredient_detail_source"),
        "image_url": payload.get("image_url"),
        "image_local_url": payload.get("image_local_url"),
        "image_source_url": payload.get("image_source_url"),
        "quality_score": payload.get("quality_score"),
        "quality_tier": payload.get("quality_tier"),
        "meal_readiness_score": payload.get("meal_readiness_score"),
        "meal_readiness_tier": payload.get("meal_readiness_tier"),
        "meal_ready": payload.get("meal_ready"),
        "consumption_state": payload.get("consumption_state"),
        "final_output_allowed": payload.get("final_output_allowed"),
        "unsafe_output_reason": payload.get("unsafe_output_reason"),
        "safe_display_name": payload.get("safe_display_name") or payload.get("name"),
        "meal_role_tags": payload.get("meal_role_tags") or [],
        "meal_role_primary": payload.get("meal_role_primary"),
        "planner_rank_weight": payload.get("planner_rank_weight"),
        "meal_ready_exclusion_codes": payload.get("meal_ready_exclusion_codes") or [],
        "qdrant_ingest_eligible": payload.get("qdrant_ingest_eligible"),
        "production_retrieval_enabled": payload.get("production_retrieval_enabled"),
        "qc_severity": payload.get("qc_severity"),
        "qc_blocking_codes": payload.get("qc_blocking_codes") or [],
        "qdrant_exclusion_reasons": payload.get("qdrant_exclusion_reasons") or [],
        "production_block_reasons": payload.get("production_block_reasons") or [],
        "detail_source": payload.get("detail_source"),
        "detail_endpoint_found": payload.get("detail_endpoint_found"),
        "source_name": payload.get("source_name"),
        "source_url": payload.get("source_url"),
        "provenance": payload.get("provenance"),
        "diet_tags": payload.get("diet_tags") or [],
        "allergen_tags": payload.get("allergen_tags") or [],
        "content": payload.get("content"),
        "retrieval_score": score,
    }
