from __future__ import annotations

from typing import Any, Iterable, Optional

from .normalize import ascii_normalize


VEGAN_COMPATIBLE_NAME_MARKERS = (
    "dau den",
    "dau do",
    "dau xanh",
    "dau hu",
    "dau phu",
    "hat bi",
    "hat de",
    "hat dieu",
    "hat huong duong",
    "hat macca",
    "hat oc cho",
    "hat sen",
    "khoai",
    "sweet potato",
    "potato",
    "dau phong",
    "lac hat",
    "macadamia",
    "oc cho",
    "peanut",
    "tofu",
)

VEGETARIAN_COMPATIBLE_NAME_MARKERS = (
    *VEGAN_COMPATIBLE_NAME_MARKERS,
    "sua chua",
    "trung",
    "yogurt",
)

PESCATARIAN_COMPATIBLE_NAME_MARKERS = (
    *VEGETARIAN_COMPATIBLE_NAME_MARKERS,
    "ca ",
    "ca hoi",
    "ca lac",
    "ca ngu",
    "ca nuc",
    "ca thu",
    "muc",
    "tom",
)


def effective_diet_tags(payload: dict[str, Any]) -> list[str]:
    tags = {ascii_normalize(tag) for tag in (payload.get("diet_tags") or []) if ascii_normalize(tag)}
    text = ascii_normalize(
        " ".join(
            str(value)
            for value in [
                payload.get("name"),
                payload.get("safe_display_name"),
                payload.get("food_name"),
                payload.get("group_name"),
                payload.get("canonical_name_key"),
                payload.get("meal_family_key"),
            ]
            if value
        )
    )
    if not text:
        return sorted(tags)

    if text.startswith("hat "):
        tags.update({"vegan", "vegetarian"})
    if any(marker in text for marker in VEGAN_COMPATIBLE_NAME_MARKERS):
        tags.update({"vegan", "vegetarian"})
    elif any(marker in text for marker in VEGETARIAN_COMPATIBLE_NAME_MARKERS):
        tags.add("vegetarian")
    if any(marker in text for marker in PESCATARIAN_COMPATIBLE_NAME_MARKERS):
        tags.add("pescatarian")
    return sorted(tags)


def matches_dietary_preference(
    dietary_preference: Optional[str],
    diet_tags: Iterable[str],
    payload: Optional[dict[str, Any]] = None,
) -> bool:
    preference = ascii_normalize(dietary_preference)
    if not preference or preference == "omnivore":
        return True

    effective_tags = {ascii_normalize(tag) for tag in diet_tags if ascii_normalize(tag)}
    if payload:
        effective_tags.update(effective_diet_tags(payload))

    if preference == "vegetarian":
        return bool(effective_tags.intersection({"vegetarian", "vegan"}))
    if preference == "vegan":
        return "vegan" in effective_tags
    if preference == "pescatarian":
        return bool(effective_tags.intersection({"pescatarian", "vegetarian", "vegan"}))
    return True
