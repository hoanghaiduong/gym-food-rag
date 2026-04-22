from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Optional


COMMON_VIETNAMESE_MOJIBAKE_MAP = {
    "Ã„Â": "Đ",
    "Ã„â€˜": "đ",
    "Ä": "Đ",
    "Ä‘": "đ",
}


def normalize_unicode_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value)
    for broken_text, clean_text in COMMON_VIETNAMESE_MOJIBAKE_MAP.items():
        text = text.replace(broken_text, clean_text)
    return unicodedata.normalize("NFC", text)


def ascii_normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    cleaned = normalize_unicode_text(value).replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", cleaned)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().split())


def raw_normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(normalize_unicode_text(value).lower().split())


def raw_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"\w+", value, flags=re.UNICODE) if token}


def normalized_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value) if token}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return default
        return numeric
    except (TypeError, ValueError):
        return default


def sanitize_json_payload(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {key: sanitize_json_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_payload(item) for item in value]
    return value


def format_metric(value: Any) -> Optional[str]:
    numeric = safe_float(value, None)
    if numeric is None:
        return None
    if float(numeric).is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".")
