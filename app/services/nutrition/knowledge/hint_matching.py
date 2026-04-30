from __future__ import annotations

import re
from typing import Any, Callable

from .normalize import ascii_normalize


_ROLE_TAG_BY_HINT_ROLE = {
    "protein": "protein_anchor",
    "carb": "carb_anchor",
    "produce": "produce_support",
}

_HINT_ROLE_OVERRIDES = {
    "ca": "protein",
    "ca hoi": "protein",
    "ca ngu": "protein",
    "ca nuc": "protein",
    "trung": "protein",
    "ga": "protein",
    "thit ga": "protein",
    "uc ga": "protein",
    "dau hu": "protein",
    "dau phu": "protein",
    "tofu": "protein",
    "gao": "carb",
    "com": "carb",
    "gao lut": "carb",
    "khoai": "carb",
    "khoai lang": "carb",
    "bun tuoi": "carb",
    "ngo": "carb",
    "bap": "carb",
    "rau xanh": "produce",
    "trai cay": "produce",
    "hoa qua": "produce",
}

_FISH_TOKENS = {"ca", "fish", "salmon", "tuna", "nuc", "hoi", "bass", "snapper"}
_NON_FISH_SEAFOOD_TOKENS = {
    "muc",
    "squid",
    "cuttle",
    "tom",
    "shrimp",
    "prawn",
    "so",
    "cockle",
    "hau",
    "oyster",
    "oc",
    "snail",
    "cua",
    "crab",
    "clam",
    "hen",
    "scallop",
    "lobster",
}
_FRUIT_NAME_TOKENS = {
    "chuoi",
    "banana",
    "tao",
    "apple",
    "nho",
    "grape",
    "orange",
    "xoai",
    "mango",
    "mit",
    "jackfruit",
    "pineapple",
    "pear",
    "buoi",
    "pomelo",
}
_STARCH_TOKENS = {
    "gao",
    "com",
    "rice",
    "xoi",
    "bun",
    "mien",
    "mi",
    "pho",
    "nui",
    "noodle",
    "pasta",
    "oat",
    "yen",
    "mach",
    "ngo",
    "bap",
    "corn",
    "khoai",
    "potato",
    "cassava",
    "san",
}
_ANIMAL_PROTEIN_TOKENS = {
    "ga",
    "chicken",
    "poultry",
    "bo",
    "beef",
    "heo",
    "lon",
    "pork",
    "vit",
    "duck",
    "de",
    "goat",
    "trau",
    "buffalo",
}
_GREENS_EXPLICIT_TOKENS = {
    "rau",
    "cai",
    "vegetable",
    "vegetables",
    "greens",
    "spinach",
    "amaranth",
    "salad",
    "xalach",
    "gia",
}
_EGG_SOURCE_TOKENS = {"ga", "vit", "cut", "cun", "chim", "egg"}
_ROOT_DIRECT_TOKENS = {"khoai", "potato", "carrot", "san", "cassava"}


def _tokenize(value: Any) -> set[str]:
    normalized = ascii_normalize(value)
    if not normalized:
        return set()
    return {token for token in re.sub(r"[^a-z0-9]+", " ", normalized).split() if token}


def _candidate_primary_tokens(candidate: dict[str, Any]) -> set[str]:
    return _tokenize(
        " ".join(
            str(value)
            for value in [
                candidate.get("name") or candidate.get("food_name"),
                candidate.get("name_en"),
                candidate.get("meal_family_key"),
                candidate.get("canonical_name_key"),
            ]
            if value
        )
    )


def _candidate_group_tokens(candidate: dict[str, Any]) -> set[str]:
    return _tokenize(candidate.get("group_name"))


def _candidate_search_tokens(candidate: dict[str, Any]) -> set[str]:
    return _candidate_primary_tokens(candidate) | _candidate_group_tokens(candidate)


def _candidate_role_tags(candidate: dict[str, Any]) -> set[str]:
    return set(candidate.get("meal_role_tags") or [])


def _candidate_has_role(candidate: dict[str, Any], expected_role: str) -> bool:
    role_tag = _ROLE_TAG_BY_HINT_ROLE.get(expected_role)
    if not role_tag:
        return True
    return role_tag in _candidate_role_tags(candidate)


def _matches_fish(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "protein"):
        return False
    tokens = _candidate_search_tokens(candidate)
    if not tokens or tokens & _NON_FISH_SEAFOOD_TOKENS:
        return False
    return bool(tokens & _FISH_TOKENS)


def _matches_specific_fish(candidate: dict[str, Any], required_tokens: set[str]) -> bool:
    tokens = _candidate_search_tokens(candidate)
    return _matches_fish(candidate) and required_tokens.issubset(tokens)


def _matches_egg(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "protein"):
        return False
    tokens = _candidate_search_tokens(candidate)
    if not tokens:
        return False
    if "egg" in tokens and not (tokens & {"plant", "aubergine"}):
        return True
    if "trung" not in tokens:
        return False
    if tokens & {"dau", "bean", "soy", "seed", "hat"} and not (tokens & _EGG_SOURCE_TOKENS):
        return False
    return bool(tokens & _EGG_SOURCE_TOKENS)


def _matches_chicken(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "protein"):
        return False
    tokens = _candidate_search_tokens(candidate)
    return bool(tokens & {"ga", "chicken", "poultry"})


def _matches_chicken_breast(candidate: dict[str, Any]) -> bool:
    tokens = _candidate_search_tokens(candidate)
    return _matches_chicken(candidate) and bool(tokens & {"uc", "breast", "luon"})


def _matches_tofu(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "protein"):
        return False
    tokens = _candidate_search_tokens(candidate)
    return "tofu" in tokens or {"dau", "hu"}.issubset(tokens) or {"dau", "phu"}.issubset(tokens)


def _matches_rice(candidate: dict[str, Any]) -> bool:
    tokens = _candidate_search_tokens(candidate)
    return bool(tokens & {"gao", "com", "rice", "xoi", "chao"})


def _matches_brown_rice(candidate: dict[str, Any]) -> bool:
    tokens = _candidate_search_tokens(candidate)
    return _matches_rice(candidate) and bool(tokens & {"lut", "brown"})


def _matches_corn(candidate: dict[str, Any]) -> bool:
    tokens = _candidate_search_tokens(candidate)
    return bool(tokens & {"ngo", "bap", "corn"})


def _matches_root_starch(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "carb"):
        return False
    tokens = _candidate_primary_tokens(candidate)
    if not tokens:
        return False
    if tokens & {"rau", "leaf", "leaves", "greens"}:
        return False
    return bool(tokens & {"khoai", "potato", "cassava", "san"})


def _matches_sweet_potato(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "carb"):
        return False
    tokens = _candidate_primary_tokens(candidate)
    if not tokens or tokens & {"rau", "leaf", "leaves", "greens"}:
        return False
    return {"khoai", "lang"}.issubset(tokens) or {"sweet", "potato"}.issubset(tokens)


def _matches_bun_tuoi(candidate: dict[str, Any]) -> bool:
    tokens = _candidate_search_tokens(candidate)
    return "bun" in tokens and "tuoi" in tokens


def _matches_greens(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "produce"):
        return False
    tokens = _candidate_search_tokens(candidate)
    if not tokens or tokens & _FRUIT_NAME_TOKENS or tokens & _NON_FISH_SEAFOOD_TOKENS:
        return False
    if tokens & {"kho", "dried", "hat", "seed", "seeds"}:
        return False
    if tokens & _STARCH_TOKENS and "gia" not in tokens:
        return False
    if tokens & _ANIMAL_PROTEIN_TOKENS:
        return False
    if tokens & _ROOT_DIRECT_TOKENS or {"ca", "rot"}.issubset(tokens):
        return False
    if tokens & _GREENS_EXPLICIT_TOKENS:
        return True
    if any(
        required.issubset(tokens)
        for required in [
            {"co", "ve"},
            {"dua", "leo"},
            {"ca", "chua"},
            {"ca", "bat"},
            {"ca", "tim"},
            {"sup", "lo"},
            {"mong", "toi"},
            {"cai", "ngong"},
        ]
    ):
        return True
    return True


def _matches_fruit(candidate: dict[str, Any]) -> bool:
    if not _candidate_has_role(candidate, "produce"):
        return False
    tokens = _candidate_primary_tokens(candidate)
    if not tokens or tokens & _NON_FISH_SEAFOOD_TOKENS or tokens & _ANIMAL_PROTEIN_TOKENS:
        return False
    if tokens & _FRUIT_NAME_TOKENS:
        return True
    if "fruit" in tokens:
        return True
    return {"trai", "cay"}.issubset(tokens) or {"qua", "chin"}.issubset(tokens)


_RUNTIME_HINT_MATCHERS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "ca": _matches_fish,
    "ca hoi": lambda candidate: _matches_specific_fish(candidate, {"hoi"}),
    "ca ngu": lambda candidate: _matches_specific_fish(candidate, {"ngu"}),
    "ca nuc": lambda candidate: _matches_specific_fish(candidate, {"nuc"}),
    "trung": _matches_egg,
    "ga": _matches_chicken,
    "thit ga": _matches_chicken,
    "uc ga": _matches_chicken_breast,
    "dau hu": _matches_tofu,
    "dau phu": _matches_tofu,
    "tofu": _matches_tofu,
    "gao": _matches_rice,
    "com": _matches_rice,
    "gao lut": _matches_brown_rice,
    "khoai": _matches_root_starch,
    "khoai lang": _matches_sweet_potato,
    "ngo": _matches_corn,
    "bap": _matches_corn,
    "bun tuoi": _matches_bun_tuoi,
    "rau xanh": _matches_greens,
    "trai cay": _matches_fruit,
    "hoa qua": _matches_fruit,
}


def candidate_matches_runtime_hint(candidate: dict[str, Any], hint: str) -> bool | None:
    normalized_hint = ascii_normalize(hint)
    if not normalized_hint:
        return False
    matcher = _RUNTIME_HINT_MATCHERS.get(normalized_hint)
    if matcher is None:
        return None
    expected_role = _HINT_ROLE_OVERRIDES.get(normalized_hint)
    if expected_role and not _candidate_has_role(candidate, expected_role):
        return False
    return matcher(candidate)
