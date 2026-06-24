import json
from typing import Any

_MISSING = object()


def dumps_json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def loads_json(value: Any, default: Any = _MISSING) -> Any:
    fallback = {} if default is _MISSING else default
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback
