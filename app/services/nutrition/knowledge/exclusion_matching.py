from __future__ import annotations

import re

from .normalize import ascii_normalize


PEANUT_EXCLUSION_HINTS = {"dau phong", "lac", "peanut"}
PEANUT_NAME_MARKERS = ("dau phong", "peanut", "bo dau phong", "lac hat", "xoi lac")
PEANUT_FALSE_POSITIVE_PHRASES = ("ca lac",)


def _tokenize(value: str) -> list[str]:
    return [token for token in re.sub(r"[^a-z0-9]+", " ", value).split() if token]


def _matches_peanut_exclusion(normalized_text: str) -> bool:
    if any(marker in normalized_text for marker in PEANUT_NAME_MARKERS):
        return True
    if any(phrase in normalized_text for phrase in PEANUT_FALSE_POSITIVE_PHRASES):
        return False
    return "lac" in set(_tokenize(normalized_text))


def normalized_text_matches_exclusion(normalized_text: str, exclusion: str) -> bool:
    normalized_exclusion = ascii_normalize(exclusion)
    if not normalized_text or not normalized_exclusion:
        return False
    if normalized_exclusion in PEANUT_EXCLUSION_HINTS:
        return _matches_peanut_exclusion(normalized_text)

    text_tokens = set(_tokenize(normalized_text))
    exclusion_tokens = _tokenize(normalized_exclusion)
    if not exclusion_tokens:
        return False
    if len(exclusion_tokens) == 1:
        return exclusion_tokens[0] in text_tokens
    return all(token in text_tokens for token in exclusion_tokens)
