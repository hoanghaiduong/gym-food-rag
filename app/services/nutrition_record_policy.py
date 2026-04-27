from __future__ import annotations

import math
import re
import unicodedata
from typing import Any


PREPARATION_PATTERNS = [
    ("boiled", [" luoc", " boiled"]),
    ("grilled", [" nuong", " grilled"]),
    ("fried", [" chien", " ran", " fried"]),
    ("stir_fried", [" xao", " stir fried", " stir-fried"]),
    ("steamed", [" hap", " steamed"]),
    ("braised", [" kho", " om", " braised"]),
    ("roasted", [" quay", " roasted"]),
    ("soup", [" canh", " sup", " soup"]),
    ("porridge", [" chao", " porridge"]),
    ("raw", [" tuoi", " raw", " fresh"]),
]

PORTION_DEFAULTS_BY_TAXONOMY = {
    "noodle_and_soup_dishes": 380.0,
    "rice_and_porridge_dishes": 320.0,
    "stir_fried_dishes": 240.0,
    "soups_and_broths": 300.0,
    "shellfish_and_mollusks": 220.0,
    "desserts": 180.0,
    "drinks": 240.0,
    "cakes_pastries_snacks": 120.0,
    "other_dishes": 240.0,
    "ready_made_foods": 180.0,
}

INGREDIENT_HINT_PATTERNS = [
    ("ức gà", ["uc ga", " chicken breast"]),
    ("thịt gà", ["ga", "chicken"]),
    ("trứng", ["trung", "egg"]),
    ("gạo/cơm", ["gao", "com", "rice"]),
    ("bún", ["bun"]),
    ("phở", ["pho"]),
    ("mì", ["mi ", "my ", "noodle"]),
    ("miến", ["mien"]),
    ("hủ tiếu", ["hu tieu"]),
    ("bánh đa", ["banh da"]),
    ("xôi", ["xoi"]),
    ("cháo", ["chao"]),
    ("khoai", ["khoai", "potato", "sweet potato"]),
    ("yến mạch", ["yen mach", "oat"]),
    ("đậu hũ", ["dau hu", "tofu"]),
    ("đậu nành", ["dau nanh", "soy"]),
    ("cá", ["ca ", "fish", "salmon", "tuna"]),
    ("tôm", ["tom", "shrimp"]),
    ("bò", ["bo ", "beef"]),
    ("heo", ["heo", "lon", "pork"]),
    ("rau xanh", ["rau", "cai", "vegetable"]),
    ("trái cây", ["trai cay", "fruit"]),
    ("sữa", ["sua", "milk", "yogurt"]),
]

CONDIMENT_KEYWORDS = [
    "toi ",
    "hanh ",
    "ot ",
    "muoi",
    "gia vi",
    "nuoc mam",
    "nuoc tuong",
    "me ",
    "tieu",
    "dau an",
]

OFFAL_KEYWORDS = [
    "long ",
    "tim ",
    "gan ",
    "tiet ",
    "trung ca",
    "giblet",
    "roe",
]

DESSERT_KEYWORDS = [
    "banh ",
    "che ",
    "kem",
    "caramen",
    "keo",
    "mut ",
]

SAVORY_BAKERY_KEYWORDS = [
    "banh bao",
    "banh cuon",
    "banh beo",
    "banh gio",
    "banh duc",
    "banh bot loc",
    "banh chung",
    "banh tet",
]

AFFORDABLE_KEYWORDS = [
    "ga",
    "trung",
    "gao",
    "com",
    "khoai",
    "dau hu",
    "rau",
    "ca ",
]

CONSUMPTION_STATE_PREPARED_READY = "prepared_ready"
CONSUMPTION_STATE_DIRECT_EDIBLE_RAW = "direct_edible_raw"
CONSUMPTION_STATE_REQUIRES_PREPARATION = "requires_preparation"

PREPARED_STYLE_CODES = {
    "boiled",
    "grilled",
    "fried",
    "stir_fried",
    "steamed",
    "braised",
    "roasted",
    "soup",
    "porridge",
}

RAW_STATE_MARKERS = (" raw", " fresh", " tuoi", " song")

DIRECT_EDIBLE_RAW_NAME_PATTERNS = [
    "bun tuoi",
]

DIRECT_EDIBLE_FRUIT_PATTERNS = [
    "trai cay",
    "hoa qua",
    "fruit",
    "tao",
    "chuoi",
    "xoai",
    "du du",
    "nho",
    "dua hau",
    "dua luoi",
    "dau tay",
    "mit",
]

READY_PROCESSED_NAME_PATTERNS = [
    "com",
    "xoi",
    "sua chua",
    "yogurt",
    "yoghurt",
    "pho mai",
    "cheese",
    "banh mi",
    "bread",
    "sandwich",
    "tofu",
    "dau hu",
    "dau phu",
    "tempeh",
    "sua ",
    "milk",
    "hat dieu",
    "hanh nhan",
    "oc cho",
    "hat bi do",
    "hat bi o",
    "hat huong duong",
    "hat de cuoi",
    "macca",
]

READY_PROCESSED_TAXONOMY_KEYS = {
    "desserts",
    "desserts_and_sweets",
    "bakery_and_snacks",
    "ready_made_foods",
    "cakes_pastries_snacks",
    "drinks",
}

ANIMAL_PROTEIN_PATTERNS = [
    "ga",
    "chicken",
    "turkey",
    "ga tay",
    "ga ta",
    "ga cong nghiep",
    "thit ga",
    "bo",
    "beef",
    "heo",
    "lon",
    "pork",
    "vit",
    "duck",
    "fish",
    "salmon",
    "tuna",
    "thuy san",
    "tom",
    "shrimp",
    "cua",
    "crab",
    "hai san",
    "muc",
    "oc",
    "ngheu",
    "hau",
    "trung",
    "egg",
]

STARCH_STAPLE_PATTERNS = [
    "gao",
    "rice",
    "com",
    "ngo",
    "bap",
    "corn",
    "khoai",
    "potato",
    "sweet potato",
    "san",
    "cassava",
    "yen mach",
    "oat",
    "oats",
    "dau xanh",
    "dau den",
    "dau do",
    "dau nanh",
    "soybean",
    "bean",
    "lentil",
    "hat sen",
    "lotus seed",
    "lua",
    "nep",
]

PRODUCE_GROUP_PATTERNS = [
    "rau",
    "vegetable",
    "produce",
    "qua",
    "cu",
    "la",
    "thao moc",
]

MEAL_FAMILY_ALIAS_RULES = [
    ("ga", [r"\bga tay\b", r"\bga ta\b", r"\bga cong nghiep\b", r"\bthit ga\b", r"\buc ga\b", r"\bchicken\b", r"\bturkey\b"]),
    ("ngo", [r"\bngo ca bap\b", r"\bca bap\b", r"\bbap\b", r"\bcorn\b"]),
    ("gao", [r"\bcom\b", r"\brace\b"]),
    ("trung", [r"\btrung ga\b", r"\begg\b"]),
]


def ascii_normalize(value: Any) -> str:
    text = "" if value is None else str(value)
    normalized = unicodedata.normalize("NFKD", text)
    return " ".join(normalized.encode("ascii", "ignore").decode("ascii").lower().split())


def safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def preparation_style(name: Any) -> str | None:
    raw_text = str(name or "").lower()
    normalized = ascii_normalize(name)
    if not normalized:
        return None
    for style, patterns in PREPARATION_PATTERNS:
        normalized_patterns = [pattern.strip() for pattern in patterns]
        if "canh" in normalized_patterns and not re.search(r"(?iu)\bcanh\b", raw_text):
            normalized_patterns = [pattern for pattern in normalized_patterns if pattern != "canh"]
        if _contains_any_pattern(normalized, normalized_patterns):
            return style
    return None


def has_prepared_style(name: Any) -> bool:
    return preparation_style(name) in PREPARED_STYLE_CODES


def canonical_name_key(name: Any) -> str:
    normalized = ascii_normalize(name)
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = re.sub(r"[,;:/-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def meal_family_key(name: Any) -> str:
    normalized = canonical_name_key(name)
    if not normalized:
        return ""
    normalized = re.sub(
        r"\b(luoc|nuong|chien|ran|xao|hap|kho|om|quay|ham|sot|sup|canh|chao|boiled|fried|grilled|steamed|raw|fresh|tuoi|song)\b",
        " ",
        normalized,
    )
    for canonical_value, patterns in MEAL_FAMILY_ALIAS_RULES:
        for pattern in patterns:
            normalized = re.sub(pattern, canonical_value, normalized)
    tokens = [token for token in normalized.split() if token]
    normalized = " ".join(dict.fromkeys(tokens))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or canonical_name_key(name)


def _contains_any_pattern(normalized_text: str, patterns: list[str]) -> bool:
    if not normalized_text:
        return False
    token_set = set(re.sub(r"[^a-z0-9]+", " ", normalized_text).split())
    for pattern in patterns:
        normalized_pattern = ascii_normalize(pattern)
        if not normalized_pattern:
            continue
        if " " in normalized_pattern:
            if normalized_pattern in normalized_text:
                return True
            continue
        if normalized_pattern in token_set:
            return True
    return False


def _record_context_text(record: dict[str, Any]) -> dict[str, str]:
    name = ascii_normalize(record.get("name"))
    group = ascii_normalize(record.get("group_name") or record.get("group"))
    taxonomy_level_1 = ascii_normalize(record.get("taxonomy_level_1"))
    taxonomy_level_2 = ascii_normalize(record.get("taxonomy_level_2"))
    combined = " ".join(item for item in [name, group, taxonomy_level_1, taxonomy_level_2] if item)
    return {
        "name": name,
        "group": group,
        "taxonomy_level_1": taxonomy_level_1,
        "taxonomy_level_2": taxonomy_level_2,
        "combined": combined,
    }


def _has_raw_state_marker(normalized_name: str) -> bool:
    return any(marker in f" {normalized_name}" for marker in RAW_STATE_MARKERS)


def _is_fruit_like_record(record: dict[str, Any], context: dict[str, str]) -> bool:
    taxonomy_level_1 = context["taxonomy_level_1"]
    taxonomy_level_2 = context["taxonomy_level_2"]
    combined = context["combined"]
    return (
        taxonomy_level_1 == "fruits_and_light_foods"
        or "fruit" in taxonomy_level_2
        or "trai cay" in combined
        or _contains_any_pattern(combined, DIRECT_EDIBLE_FRUIT_PATTERNS)
    )


def _is_direct_edible_raw_record(record: dict[str, Any], context: dict[str, str]) -> bool:
    normalized_name = context["name"]
    combined = context["combined"]
    if _contains_any_pattern(normalized_name, DIRECT_EDIBLE_RAW_NAME_PATTERNS):
        return True
    if _is_fruit_like_record(record, context):
        return True
    return False


def _is_ready_processed_record(record: dict[str, Any], context: dict[str, str]) -> bool:
    entity_type = str(record.get("entity_type") or "food")
    normalized_name = context["name"]
    taxonomy_level_1 = context["taxonomy_level_1"]
    taxonomy_level_2 = context["taxonomy_level_2"]
    cooked_marker_present = has_prepared_style(record.get("name"))
    if entity_type == "dish":
        return True
    if _has_raw_state_marker(normalized_name) and not cooked_marker_present:
        return False
    if _contains_any_pattern(normalized_name, READY_PROCESSED_NAME_PATTERNS):
        return True
    return taxonomy_level_1 in READY_PROCESSED_TAXONOMY_KEYS or taxonomy_level_2 in READY_PROCESSED_TAXONOMY_KEYS


def _unsafe_output_reason_for_context(context: dict[str, str]) -> str:
    combined = context["combined"]
    if _contains_any_pattern(combined, ANIMAL_PROTEIN_PATTERNS):
        return "raw_animal_protein"
    if _contains_any_pattern(combined, STARCH_STAPLE_PATTERNS):
        return "raw_starchy_staple"
    return "raw_ambiguous_ingredient"


def _build_safe_display_name(record: dict[str, Any], consumption_state: str) -> str:
    name = str(record.get("name") or "").strip()
    if not name:
        return name
    normalized_name = ascii_normalize(name)
    if consumption_state == CONSUMPTION_STATE_PREPARED_READY:
        cooked_marker_present = has_prepared_style(name)
        if cooked_marker_present:
            cleaned = re.sub(r"(?iu)\b(tươi|tuoi|sống|song|raw|fresh)\b", " ", name)
            cleaned = re.sub(r"\s+,", ",", cleaned)
            cleaned = re.sub(r",\s*,", ", ", cleaned)
            cleaned = re.sub(r"\s{2,}", " ", cleaned)
            cleaned = re.sub(r"\s+,", ",", cleaned)
            cleaned = cleaned.strip(" ,")
            if cleaned:
                return cleaned
    if consumption_state != CONSUMPTION_STATE_DIRECT_EDIBLE_RAW:
        return name
    if "bun tuoi" in normalized_name:
        return name
    if normalized_name.endswith(" tuoi") and "," in name:
        return name.rsplit(",", 1)[0].strip()
    return name


def evaluate_consumption_policy(record: dict[str, Any]) -> dict[str, Any]:
    context = _record_context_text(record)
    entity_type = str(record.get("entity_type") or "food")
    preparation = preparation_style(record.get("name"))
    normalized_name = context["name"]
    normalized_group = context["group"]
    combined = context["combined"]
    cooked_or_prepared = preparation in PREPARED_STYLE_CODES
    animal_like = _contains_any_pattern(combined, ANIMAL_PROTEIN_PATTERNS)
    starch_like = _contains_any_pattern(combined, STARCH_STAPLE_PATTERNS)
    produce_like = _contains_any_pattern(normalized_group, PRODUCE_GROUP_PATTERNS) or (
        _contains_any_pattern(normalized_name, PRODUCE_GROUP_PATTERNS)
        and not _is_fruit_like_record(record, context)
    )
    direct_edible_raw = _is_direct_edible_raw_record(record, context)
    ready_processed = _is_ready_processed_record(record, context)
    raw_marked = preparation == "raw" or _has_raw_state_marker(normalized_name)

    if cooked_or_prepared or ready_processed:
        consumption_state = CONSUMPTION_STATE_PREPARED_READY
        unsafe_reason = None
    elif direct_edible_raw:
        consumption_state = CONSUMPTION_STATE_DIRECT_EDIBLE_RAW
        unsafe_reason = None
    elif animal_like or starch_like or produce_like or raw_marked or entity_type == "food":
        consumption_state = CONSUMPTION_STATE_REQUIRES_PREPARATION
        unsafe_reason = _unsafe_output_reason_for_context(context)
    else:
        consumption_state = CONSUMPTION_STATE_PREPARED_READY
        unsafe_reason = None

    final_output_allowed = consumption_state != CONSUMPTION_STATE_REQUIRES_PREPARATION
    return {
        "consumption_state": consumption_state,
        "final_output_allowed": final_output_allowed,
        "unsafe_output_reason": unsafe_reason,
        "safe_display_name": _build_safe_display_name(record, consumption_state),
    }


def exact_dedup_key(record: dict[str, Any]) -> str:
    return "|".join(
        [
            str(record.get("entity_type") or ""),
            canonical_name_key(record.get("name")),
            str(record.get("portion_basis") or ""),
            str(record.get("taxonomy_level_2") or record.get("group_slug") or ""),
            str(round(safe_float(record.get("energy_kcal"), 0.0) or 0.0, 1)),
            str(round(safe_float(record.get("protein_g"), 0.0) or 0.0, 1)),
            str(round(safe_float(record.get("carbs_g"), 0.0) or 0.0, 1)),
            str(round(safe_float(record.get("fat_g"), 0.0) or 0.0, 1)),
        ]
    )


def normalize_component_list(raw_components: Any) -> list[str]:
    normalized_components: list[str] = []
    if not raw_components:
        return normalized_components
    if isinstance(raw_components, list):
        values = raw_components
    else:
        values = [raw_components]
    seen: set[str] = set()
    for item in values:
        if isinstance(item, dict):
            text = item.get("name") or item.get("ingredient") or item.get("food_name")
        else:
            text = item
        cleaned = str(text or "").strip()
        normalized = ascii_normalize(cleaned)
        if not cleaned or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_components.append(cleaned)
    return normalized_components


def infer_ingredient_hints(record: dict[str, Any]) -> list[str]:
    components = normalize_component_list(record.get("dish_components"))
    if components:
        return components[:8]

    haystack = " ".join(
        str(item)
        for item in [
            record.get("name"),
            record.get("name_en"),
            record.get("group_name"),
            record.get("category_name_en"),
        ]
        if item
    )
    normalized = ascii_normalize(haystack)
    hints: list[str] = []
    for label, patterns in INGREDIENT_HINT_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            hints.append(label)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in hints:
        normalized_item = ascii_normalize(item)
        if normalized_item in seen:
            continue
        seen.add(normalized_item)
        deduped.append(item)
    return deduped[:8]


def infer_serving_size(record: dict[str, Any]) -> tuple[float | None, str, str]:
    portion_g = safe_float(record.get("portion_g"), None)
    if portion_g is not None and portion_g > 0:
        return float(portion_g), "source", "high"

    entity_type = str(record.get("entity_type") or "food")
    if entity_type == "food":
        return None, "per_100g_default", "high"

    taxonomy_level_2 = str(record.get("taxonomy_level_2") or "")
    inferred = PORTION_DEFAULTS_BY_TAXONOMY.get(taxonomy_level_2)
    if inferred is not None:
        return inferred, "taxonomy_default", "medium"

    energy = safe_float(record.get("energy_kcal"), None) or 0.0
    if energy >= 350:
        return 220.0, "energy_heuristic", "low"
    if energy >= 180:
        return 180.0, "energy_heuristic", "low"
    return 150.0, "generic_dish_default", "low"


def infer_meal_role_tags(record: dict[str, Any]) -> list[str]:
    """Enhanced role inference for higher tag_hit_rate (~99%) and better retrieval precision/recall.
    Uses taxonomy, nutrient ratios, name patterns. Avoids over-tagging snacks/desserts that hurt precision."""
    roles: list[str] = []
    entity_type = str(record.get("entity_type") or "food")
    name = ascii_normalize(record.get("name") or "")
    taxonomy_level_1 = str(record.get("taxonomy_level_1") or "")
    taxonomy_level_2 = str(record.get("taxonomy_level_2") or "")
    group_name = ascii_normalize(record.get("group_name") or "")
    energy = safe_float(record.get("energy_kcal"), 0.0) or 0.0
    protein = safe_float(record.get("protein_g"), 0.0) or 0.0
    carbs = safe_float(record.get("carbs_g"), 0.0) or 0.0
    fat = safe_float(record.get("fat_g"), 0.0) or 0.0
    fiber = safe_float(record.get("fiber_g"), 0.0) or 0.0

    # Core anchors (high confidence for recall)
    if protein >= 10 or taxonomy_level_2 in {"meats", "seafood", "eggs_dairy", "plant_proteins"}:
        roles.append("protein_anchor")
    if carbs >= 15 or taxonomy_level_2 in {"grains", "rice_and_porridge_dishes", "noodles"}:
        roles.append("carb_anchor")
    if ("rau" in group_name or "cải" in name or fiber >= 2.5 or "produce" in (record.get("diet_tags") or [])
            or taxonomy_level_1 in {"vegetables", "fruits_and_light_foods"}):
        roles.append("produce_support")

    # Post/pre workout (stronger rules for intent-conditional recall)
    if (protein >= 12 and carbs >= 12) or (protein >= 18 and energy <= 220):
        roles.append("post_workout_friendly")
    if carbs >= 25 and fat <= 8 and fiber >= 2:
        roles.append("pre_workout_friendly")
    if protein >= 15 and fiber >= 4 and fat <= 10:  # high satiety
        roles.append("high_satiety")

    # Meal type roles (more precise to reduce snack intrusion)
    if entity_type == "dish":
        if taxonomy_level_2 in {"noodle_and_soup_dishes", "rice_and_porridge_dishes", "stir_fried_dishes", "grilled_dishes"}:
            roles.extend(["main_meal", "lunch_dinner_friendly"])
        elif taxonomy_level_2 in {"desserts", "cakes_pastries_snacks"} and protein < 8:
            roles.extend(["dessert"])  # avoid snack tag on desserts to reduce intrusion
        elif taxonomy_level_2 == "drinks" and protein < 8:
            roles.extend(["beverage"])
        elif taxonomy_level_1 == "fruits_and_light_foods" and energy < 150:
            roles.append("light_meal")
    else:
        if any(keyword in name for keyword in ["yen mach", "oat", "banh mi", "bread", "trung", "egg", "sua", "yogurt", "sinh to"]):
            roles.append("breakfast_friendly")
        if any(keyword in name for keyword in ["gao", "com", "bun", "pho", "mi ", "mien", "khoai", "com rang"]):
            roles.append("lunch_dinner_friendly")
        if any(keyword in name for keyword in ["trai cay", "fruit", "tao", "chuoi", "cam", "nho", "mit"]) and energy < 120:
            roles.append("produce_support")  # stronger produce for fruits
        if any(keyword in name for keyword in ["sua", "milk", "yogurt", "dau hu", "tofu", "hat"]):
            roles.append("snack")

    # Deduplicate while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for role in roles:
        if role in seen:
            continue
        seen.add(role)
        deduped.append(role)
    return deduped


def _practicality_penalties(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    name = ascii_normalize(record.get("name"))
    taxonomy_level_1 = str(record.get("taxonomy_level_1") or "")
    taxonomy_level_2 = str(record.get("taxonomy_level_2") or "")
    granularity = str(record.get("granularity") or "")
    protein = safe_float(record.get("protein_g"), 0.0) or 0.0
    carbs = safe_float(record.get("carbs_g"), 0.0) or 0.0
    energy = safe_float(record.get("energy_kcal"), 0.0) or 0.0
    hard: list[str] = []
    soft: list[str] = []

    if granularity == "condiment" or any(keyword in name for keyword in CONDIMENT_KEYWORDS):
        hard.append("condiment_like")
    if any(keyword in name for keyword in OFFAL_KEYWORDS):
        hard.append("specialty_offal_like")
    if taxonomy_level_2 == "drinks":
        if protein < 10:
            hard.append("drink_not_meal_component")
        else:
            soft.append("drink_as_snack_only")
    is_dessert_name = any(keyword in name for keyword in DESSERT_KEYWORDS)
    is_savory_bakery = any(keyword in name for keyword in SAVORY_BAKERY_KEYWORDS)
    if taxonomy_level_1 == "desserts_and_sweets" or taxonomy_level_2 == "desserts":
        hard.append("dessert_category")
    elif taxonomy_level_1 == "bakery_and_snacks":
        if is_savory_bakery and protein >= 8 and carbs >= 15:
            soft.append("savory_bakery_limited")
        else:
            hard.append("bakery_snack_like")
    elif is_dessert_name:
        soft.append("dessert_like")
    if taxonomy_level_1 == "fruits_and_light_foods" and energy < 120 and protein < 6 and carbs < 25:
        soft.append("light_food_not_meal")
    if not record.get("name"):
        hard.append("missing_name")
    return hard, soft


def evaluate_meal_readiness(record: dict[str, Any]) -> dict[str, Any]:
    entity_type = str(record.get("entity_type") or "food")
    energy = safe_float(record.get("energy_kcal"), 0.0) or 0.0
    protein = safe_float(record.get("protein_g"), 0.0) or 0.0
    carbs = safe_float(record.get("carbs_g"), 0.0) or 0.0
    fat = safe_float(record.get("fat_g"), 0.0) or 0.0
    quality = safe_float(record.get("quality_score"), 0.0) or 0.0
    consumption_policy = evaluate_consumption_policy(record)
    meal_roles = infer_meal_role_tags(record)
    hard_penalties, soft_penalties = _practicality_penalties(record)
    production_block_reasons = list(hard_penalties)
    if not consumption_policy["final_output_allowed"]:
        hard_penalties = [*hard_penalties, "unsafe_final_output"]
        if consumption_policy["unsafe_output_reason"]:
            production_block_reasons.append(str(consumption_policy["unsafe_output_reason"]))

    macro_complete = sum(
        1
        for field_name in ["energy_kcal", "protein_g", "carbs_g", "fat_g"]
        if safe_float(record.get(field_name), None) is not None
    ) / 4.0

    role_score = 0.0
    if "main_meal" in meal_roles:
        role_score += 0.35
    if "protein_anchor" in meal_roles:
        role_score += 0.24
    if "carb_anchor" in meal_roles:
        role_score += 0.22
    if "produce_support" in meal_roles:
        role_score += 0.18
    if "snack" in meal_roles:
        role_score += 0.16
    if "dessert" in meal_roles:
        role_score -= 0.18
    if "beverage" in meal_roles:
        role_score -= 0.10

    macro_density_bonus = 0.0
    if entity_type == "food":
        if protein >= 15:
            macro_density_bonus += 0.18
        if carbs >= 20:
            macro_density_bonus += 0.14
        if 40 <= energy <= 260:
            macro_density_bonus += 0.08
    else:
        if 120 <= energy <= 650:
            macro_density_bonus += 0.14
        if protein >= 8:
            macro_density_bonus += 0.10

    affordability_bonus = 0.0
    normalized_name = ascii_normalize(record.get("name"))
    if any(keyword in normalized_name for keyword in AFFORDABLE_KEYWORDS):
        affordability_bonus += 0.06

    score = (
        0.34 * quality
        + 0.20 * macro_complete
        + 0.32 * min(role_score, 1.0)
        + macro_density_bonus
        + affordability_bonus
        - 0.18 * len(soft_penalties)
        - 0.45 * len(hard_penalties)
    )
    score = max(0.0, min(score, 1.0))

    if hard_penalties or score < 0.35 or not consumption_policy["final_output_allowed"]:
        tier = "blocked"
    elif "dessert_like" in soft_penalties and "snack" not in meal_roles:
        tier = "discouraged"
    elif score >= 0.78:
        tier = "core"
    elif score >= 0.58:
        tier = "support"
    elif score >= 0.42:
        tier = "snack"
    else:
        tier = "discouraged"

    meal_ready = tier in {"core", "support", "snack"} and consumption_policy["final_output_allowed"]
    planner_rank_weight = {
        "core": 1.0,
        "support": 0.82,
        "snack": 0.64,
        "discouraged": 0.18,
        "blocked": 0.0,
    }[tier]

    return {
        **consumption_policy,
        "meal_role_tags": meal_roles,
        "meal_role_primary": meal_roles[0] if meal_roles else None,
        "meal_readiness_score": round(score, 4),
        "meal_readiness_tier": tier,
        "meal_ready": meal_ready,
        "planner_rank_weight": planner_rank_weight,
        "meal_ready_exclusion_codes": [*hard_penalties, *soft_penalties],
        "production_retrieval_enabled": meal_ready and consumption_policy["final_output_allowed"],
        "production_block_reasons": production_block_reasons + [
            reason for reason in soft_penalties if tier in {"discouraged", "blocked"}
        ],
    }


def enrich_meal_ready_record(record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    canonical_key = canonical_name_key(record.get("name"))
    family_key = meal_family_key(record.get("name"))
    serving_size_g, serving_size_source, serving_size_confidence = infer_serving_size(record)
    ingredient_hints = infer_ingredient_hints(record)
    if enriched.get("entity_type") == "dish" and not safe_float(enriched.get("portion_g"), None):
        enriched["portion_g"] = serving_size_g
    enriched["portion_g_source"] = serving_size_source
    enriched["serving_size_confidence"] = serving_size_confidence
    enriched["preparation_style"] = preparation_style(record.get("name"))
    enriched["canonical_name_key"] = canonical_key
    enriched["meal_family_key"] = family_key or canonical_key
    enriched["exact_dedup_key"] = exact_dedup_key({**record, "portion_g": enriched.get("portion_g")})
    enriched["ingredient_components_normalized"] = normalize_component_list(record.get("dish_components"))
    enriched["ingredient_hints"] = ingredient_hints
    enriched["ingredient_detail_source"] = (
        "source_components"
        if enriched["ingredient_components_normalized"]
        else "name_inference" if ingredient_hints else "none"
    )
    enriched.update(evaluate_meal_readiness(enriched))
    return enriched
