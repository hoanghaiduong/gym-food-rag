from __future__ import annotations

from typing import Any, Optional

from .normalize import ascii_normalize, normalized_tokens, raw_normalize, raw_tokens, safe_float


ALLERGEN_KEYWORDS = {
    "dairy": {"raw": ["sá»¯a", "phÃ´ mai"], "normalized": ["milk", "sua", "yogurt", "yoghurt", "cheese", "pho mai", "whey"]},
    "egg": {"raw": ["trá»©ng"], "normalized": ["egg", "trung"]},
    "soy": {"raw": ["Ä‘áº­u nÃ nh", "Ä‘áº­u hÅ©"], "normalized": ["soy", "soya", "dau nanh", "dau hu", "tofu"]},
    "peanut": {"raw": ["láº¡c", "Ä‘áº­u phá»™ng"], "normalized": ["peanut", "lac", "dau phong"]},
    "tree_nut": {"raw": ["háº¡t Ä‘iá»u", "háº¡nh nhÃ¢n", "Ã³c chÃ³"], "normalized": ["hat dieu", "hanh nhan", "oc cho", "pistachio", "cashew", "almond"]},
    "gluten": {"raw": [], "normalized": ["wheat", "mi", "bun mi", "bread", "pasta", "noodle"]},
    "shellfish": {"raw": ["tÃ´m", "cua", "gháº¹", "á»‘c", "má»±c"], "normalized": ["shrimp", "crab", "ghe", "oc", "muc", "shellfish"]},
    "fish": {"raw": ["cÃ¡"], "normalized": ["fish", "salmon", "tuna"]},
    "sesame": {"raw": ["mÃ¨", "vá»«ng"], "normalized": ["sesame", "vung"]},
}

ANIMAL_KEYWORDS = {
    "raw": ["bÃ²", "heo", "lá»£n", "gÃ ", "vá»‹t", "thá»‹t", "cÃ¡", "tÃ´m", "cua", "háº£i sáº£n"],
    "normalized": ["bo", "heo", "lon", "ga", "vit", "thit", "fish", "shrimp", "pork", "beef", "chicken", "duck", "hai san"],
}

PLANT_GROUP_KEYWORDS = {
    "raw": ["rau", "quáº£", "cá»§", "ngÅ© cá»‘c", "Ä‘áº­u Ä‘á»—", "háº¡t", "trÃ¡i cÃ¢y"],
    "normalized": ["vegetable", "fruit", "grain", "bean", "legume", "ngu coc", "dau do", "trai cay"],
}


def contains_keyword(
    raw_text: str,
    raw_token_set: set[str],
    normalized_text: str,
    tokens: set[str],
    keywords: dict[str, list[str]],
) -> bool:
    for keyword in keywords.get("raw", []):
        if not keyword:
            continue
        if " " in keyword:
            if keyword in raw_text:
                return True
        elif keyword in raw_token_set:
            return True
    for keyword in keywords.get("normalized", []):
        normalized_keyword = ascii_normalize(keyword)
        if not normalized_keyword:
            continue
        if " " in normalized_keyword:
            if normalized_keyword in normalized_text:
                return True
        elif normalized_keyword in tokens:
            return True
    return False


def derive_allergen_tags(record: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        str(item)
        for item in [
            record.get("name"),
            record.get("name_en"),
            record.get("group_name"),
            record.get("group"),
            " ".join(record.get("aliases", []) or []),
        ]
        if item
    )
    raw_text = raw_normalize(haystack)
    normalized = ascii_normalize(haystack)
    raw_token_set = raw_tokens(raw_text)
    tokens = normalized_tokens(normalized)
    tags: list[str] = []
    for tag, keywords in ALLERGEN_KEYWORDS.items():
        if contains_keyword(raw_text, raw_token_set, normalized, tokens, keywords):
            tags.append(tag)
    return sorted(set(tags))


def derive_diet_tags(record: dict[str, Any], allergen_tags: Optional[list[str]] = None) -> list[str]:
    allergen_tags = allergen_tags or derive_allergen_tags(record)
    name_text = " ".join(str(item) for item in [record.get("name"), record.get("name_en")] if item)
    group_text = " ".join(str(item) for item in [record.get("group_name"), record.get("group")] if item)
    combined_text = " ".join(item for item in [name_text, group_text] if item)
    normalized_name = ascii_normalize(name_text)
    raw_name = raw_normalize(name_text)
    normalized_group = ascii_normalize(group_text)
    raw_group = raw_normalize(group_text)
    normalized_combined = ascii_normalize(combined_text)
    raw_combined = raw_normalize(combined_text)
    raw_name_tokens = raw_tokens(raw_name)
    raw_group_tokens = raw_tokens(raw_group)
    raw_combined_tokens = raw_tokens(raw_combined)
    name_tokens = normalized_tokens(normalized_name)
    group_tokens = normalized_tokens(normalized_group)
    combined_tokens = normalized_tokens(normalized_combined)

    tags: list[str] = []
    if safe_float(record.get("protein_g")) >= 15:
        tags.append("high_protein")
    if safe_float(record.get("fat_g")) <= 5:
        tags.append("low_fat")
    if safe_float(record.get("carbs_g")) >= 20:
        tags.append("high_carb")

    is_plant_group = contains_keyword(raw_group, raw_group_tokens, normalized_group, group_tokens, PLANT_GROUP_KEYWORDS) or (
        not group_text and contains_keyword(raw_name, raw_name_tokens, normalized_name, name_tokens, PLANT_GROUP_KEYWORDS)
    )
    has_animal_keyword = contains_keyword(
        raw_combined,
        raw_combined_tokens,
        normalized_combined,
        combined_tokens,
        ANIMAL_KEYWORDS,
    )
    has_fish = "fish" in allergen_tags or "shellfish" in allergen_tags

    if is_plant_group and not has_animal_keyword:
        tags.append("vegetarian")
        if "dairy" not in allergen_tags and "egg" not in allergen_tags:
            tags.append("vegan")
    elif has_fish and not any(keyword in normalized_combined for keyword in ["bo", "heo", "ga", "vit", "beef", "pork", "chicken", "duck"]):
        tags.append("pescatarian")

    if is_plant_group and any(keyword in normalized_group for keyword in ["rau", "vegetable", "fruit", "trai cay"]):
        tags.append("produce")

    return sorted(set(tags))
