from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select

from app.db.tables import ai_control_versions
from app.services._json_store import loads_json


class AIRuntimeConfigService:
    def __init__(self, *, ttl_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self._loaded_at = 0.0
        self._config: dict[str, Any] = {}
        self._prompts: dict[str, str] = {}
        self._rules: dict[str, dict[str, Any]] = {}

    def get_config(self) -> dict[str, Any]:
        self._refresh_if_needed()
        return dict(self._config)

    def get_prompt(self, module: str) -> str:
        self._refresh_if_needed()
        return self._prompts.get(module, "")

    def get_rule(self, module: str) -> dict[str, Any]:
        self._refresh_if_needed()
        return dict(self._rules.get(module, {}))

    def invalidate(self) -> None:
        self._loaded_at = 0.0

    def _refresh_if_needed(self) -> None:
        if time.time() - self._loaded_at <= self.ttl_seconds:
            return
        try:
            from app.api.deps import SessionLocal

            db = SessionLocal()
            try:
                rows = db.execute(
                    select(ai_control_versions).where(ai_control_versions.c.status == "published")
                ).mappings()
                config: dict[str, Any] = {}
                prompts: dict[str, str] = {}
                rules: dict[str, dict[str, Any]] = {}
                for row in rows:
                    payload = loads_json(row["payload_json"], {})
                    if row["kind"] == "config":
                        config.update(payload)
                    elif row["kind"] == "prompt":
                        prompts[row["module"]] = str(payload.get("text") or payload.get("prompt") or "")
                    elif row["kind"] == "rule":
                        rules[row["module"]] = payload if isinstance(payload, dict) else {}
                self._config = config
                self._prompts = prompts
                self._rules = rules
            finally:
                db.close()
        except Exception:
            self._config = {}
            self._prompts = {}
            self._rules = {}
        self._loaded_at = time.time()


ai_runtime_config_service = AIRuntimeConfigService()
