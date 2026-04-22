import hashlib
import json
from typing import Any, Optional

import redis

from app.core.config import settings


class RedisStateService:
    def __init__(self):
        self.cache_ttl_seconds = settings.EXACT_CACHE_TTL_SECONDS
        self.workflow_ttl_seconds = settings.WORKFLOW_STATE_TTL_SECONDS
        self._available = True
        self.client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    def _safe(self, func, default):
        if not self._available:
            return default
        try:
            return func()
        except Exception:
            self._available = False
            return default

    def build_cache_key(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"nutrition:cache:{digest}"

    def get_cached_response(self, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        cache_key = self.build_cache_key(payload)
        raw = self._safe(lambda: self.client.get(cache_key), None)
        if not raw:
            return None
        return json.loads(raw)

    def set_cached_response(self, payload: dict[str, Any], response_data: dict[str, Any]) -> None:
        cache_key = self.build_cache_key(payload)
        serialized = json.dumps(response_data, ensure_ascii=False)
        self._safe(
            lambda: self.client.setex(cache_key, self.cache_ttl_seconds, serialized),
            None,
        )

    def save_workflow_state(self, request_id: str, state_payload: dict[str, Any]) -> None:
        serialized = json.dumps(state_payload, ensure_ascii=False)
        key = f"nutrition:workflow:{request_id}"
        self._safe(
            lambda: self.client.setex(key, self.workflow_ttl_seconds, serialized),
            None,
        )

    def get_workflow_state(self, request_id: str) -> Optional[dict[str, Any]]:
        key = f"nutrition:workflow:{request_id}"
        raw = self._safe(lambda: self.client.get(key), None)
        if not raw:
            return None
        return json.loads(raw)


redis_state_service = RedisStateService()
