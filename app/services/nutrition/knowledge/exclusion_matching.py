from __future__ import annotations

import re
from typing import Any

from .normalize import ascii_normalize


PEANUT_EXCLUSION_HINTS = {"dau phong", "lac", "peanut"}
PEANUT_NAME_MARKERS = ("dau phong", "peanut", "bo dau phong", "lac hat", "xoi lac")
PEANUT_FALSE_POSITIVE_PHRASES = ("ca lac",)

SEAFOOD_EXCLUSION_HINTS = {"hai san", "do bien", "seafood"}
FISH_EXCLUSION_HINTS = {"ca", "fish"}
SHELLFISH_EXCLUSION_HINTS = {
    "tom",
    "tep",
    "cua",
    "ghe",
    "oc",
    "muc",
    "shrimp",
    "prawn",
    "crab",
    "shellfish",
    "squid",
    "octopus",
}
SEAFOOD_ALLERGEN_TAGS = {"fish", "shellfish"}
FISH_ALLERGEN_TAGS = {"fish"}
SHELLFISH_ALLERGEN_TAGS = {"shellfish"}
SEAFOOD_NAME_MARKERS = (
    "tom",
    "tep",
    "cua",
    "ghe",
    "muc",
    "bach tuoc",
    "octopus",
    "squid",
    "shrimp",
    "prawn",
    "crab",
    "shellfish",
)
SHELLFISH_NAME_MARKERS = SEAFOOD_NAME_MARKERS + ("oc", "ngheu", "so", "hau", "hen")


def _tokenize(value: str) -> list[str]:
    return [token for token in re.sub(r"[^a-z0-9]+", " ", value).split() if token]


def _payload_text(payload: dict[str, Any]) -> str:
    values: list[str] = []
    for raw_value in [
        payload.get("name"),
        payload.get("food_name"),
        payload.get("safe_display_name"),
        payload.get("source_food_name"),
        payload.get("name_en"),
        payload.get("group_name"),
        payload.get("group_slug"),
        payload.get("category_slug"),
        " ".join(payload.get("diet_tags") or []),
        " ".join(payload.get("allergen_tags") or []),
        " ".join(payload.get("ingredient_hints") or []),
    ]:
        if raw_value:
            values.append(str(raw_value))
    return ascii_normalize(" ".join(values))


def _payload_allergen_tags(payload: dict[str, Any]) -> set[str]:
    return {ascii_normalize(tag) for tag in (payload.get("allergen_tags") or []) if tag}


def _contains_marker(normalized_text: str, marker: str) -> bool:
    marker = ascii_normalize(marker)
    if not marker:
        return False
    if " " in marker:
        return marker in normalized_text
    return marker in set(_tokenize(normalized_text))


def _matches_peanut_exclusion(normalized_text: str) -> bool:
    if any(marker in normalized_text for marker in PEANUT_NAME_MARKERS):
        return True
    if any(phrase in normalized_text for phrase in PEANUT_FALSE_POSITIVE_PHRASES):
        return False
    return "lac" in set(_tokenize(normalized_text))


def _matches_seafood_exclusion(
    normalized_text: str,
    allergen_tags: set[str],
    *,
    include_fish: bool,
    include_shellfish: bool,
) -> bool:
    if include_fish and allergen_tags.intersection(FISH_ALLERGEN_TAGS):
        return True
    if include_shellfish and allergen_tags.intersection(SHELLFISH_ALLERGEN_TAGS):
        return True
    if include_fish and include_shellfish and allergen_tags.intersection(SEAFOOD_ALLERGEN_TAGS):
        return True
    if include_shellfish and any(_contains_marker(normalized_text, marker) for marker in SHELLFISH_NAME_MARKERS):
        return True
    if include_fish and any(_contains_marker(normalized_text, marker) for marker in ("fish", "cha ca", "trung ca")):
        return True
    return False


def normalized_text_matches_exclusion(normalized_text: str, exclusion: str) -> bool:
    normalized_exclusion = ascii_normalize(exclusion)
    if not normalized_text or not normalized_exclusion:
        return False
    if normalized_exclusion in PEANUT_EXCLUSION_HINTS:
        return _matches_peanut_exclusion(normalized_text)
    if normalized_exclusion in SEAFOOD_EXCLUSION_HINTS:
        return _matches_seafood_exclusion(
            normalized_text,
            set(),
            include_fish=True,
            include_shellfish=True,
        )
    if normalized_exclusion in FISH_EXCLUSION_HINTS:
        return _matches_seafood_exclusion(
            normalized_text,
            set(),
            include_fish=True,
            include_shellfish=False,
        )
    if normalized_exclusion in SHELLFISH_EXCLUSION_HINTS:
        return _matches_seafood_exclusion(
            normalized_text,
            set(),
            include_fish=False,
            include_shellfish=True,
        )

    text_tokens = set(_tokenize(normalized_text))
    exclusion_tokens = _tokenize(normalized_exclusion)
    if not exclusion_tokens:
        return False
    if len(exclusion_tokens) == 1:
        return exclusion_tokens[0] in text_tokens
    return all(token in text_tokens for token in exclusion_tokens)


def payload_matches_exclusion(payload: dict[str, Any], exclusion: str) -> bool:
    normalized_exclusion = ascii_normalize(exclusion)
    if not normalized_exclusion:
        return False

    normalized_text = _payload_text(payload)
    allergen_tags = _payload_allergen_tags(payload)
    if normalized_exclusion in SEAFOOD_EXCLUSION_HINTS:
        return _matches_seafood_exclusion(
            normalized_text,
            allergen_tags,
            include_fish=True,
            include_shellfish=True,
        )
    if normalized_exclusion in FISH_EXCLUSION_HINTS:
        return _matches_seafood_exclusion(
            normalized_text,
            allergen_tags,
            include_fish=True,
            include_shellfish=False,
        )
    if normalized_exclusion in SHELLFISH_EXCLUSION_HINTS:
        return _matches_seafood_exclusion(
            normalized_text,
            allergen_tags,
            include_fish=False,
            include_shellfish=True,
        )
    return normalized_text_matches_exclusion(normalized_text, normalized_exclusion)
