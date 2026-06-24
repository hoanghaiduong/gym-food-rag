from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.db.tables import ai_control_versions, ai_feedback_events, audit_events
from app.schemas.ai_control import AIConfigUpdate, AIControlVersionCreate, AIFeedbackCreate
from app.services._json_store import dumps_json, loads_json


FORBIDDEN_CONFIG_TOKENS = ("KEY", "SECRET", "PASSWORD", "TOKEN")
ALLOWED_CONFIG_KEYS = {
    "GEMINI_MODEL",
    "GEMINI_MAX_RETRIES",
    "GEMINI_RETRY_BASE_SECONDS",
    "GEMINI_RETRY_MAX_SECONDS",
    "GEMINI_QUOTA_COOLDOWN_SECONDS",
    "OPENAI_MODEL",
    "OPENAI_REQUEST_TIMEOUT_SECONDS",
    "OPENAI_MAX_RETRIES",
    "OPENAI_RETRY_BASE_SECONDS",
    "OPENAI_RETRY_MAX_SECONDS",
    "OLLAMA_MODEL",
    "OLLAMA_REQUEST_TIMEOUT_SECONDS",
    "RETRIEVAL_ENABLE_LLM_QUERY_REWRITE",
    "NUTRITION_AGENT_ENABLED",
}
FORBIDDEN_POLICY_PHRASES = (
    "ignore allergy",
    "bypass allergy",
    "disable allergy",
    "ignore dietary",
    "bypass validation",
    "disable validation",
    "allow raw",
    "raw poultry",
    "raw seafood",
    "final_output_allowed=false",
    "bo qua di ung",
    "bo qua an toan",
    "cho phep do song",
    "thit song",
)


class AIControlService:
    def list_versions(self, db: Session, *, kind: str | None = None, module: str | None = None) -> list[dict[str, Any]]:
        query = select(ai_control_versions)
        if kind:
            query = query.where(ai_control_versions.c.kind == kind)
        if module:
            query = query.where(ai_control_versions.c.module == module)
        rows = db.execute(query.order_by(ai_control_versions.c.id.desc())).mappings()
        return [self._decode_version(dict(row)) for row in rows]

    def create_version(
        self,
        db: Session,
        *,
        kind: str,
        payload: AIControlVersionCreate,
        actor_user_id: int,
    ) -> dict[str, Any]:
        version = self._new_version()
        result = db.execute(
            insert(ai_control_versions).values(
                kind=kind,
                module=payload.module,
                version=version,
                payload_json=dumps_json(payload.payload),
                status="draft",
                created_by=actor_user_id,
            )
        )
        version_id = int(result.inserted_primary_key[0])
        self._audit(db, actor_user_id=actor_user_id, action=f"ai.{kind}.create", target_id=str(version_id), after=payload.payload)
        db.commit()
        return self.get_version(db, version_id=version_id)

    def upsert_config(self, db: Session, *, payload: AIConfigUpdate, actor_user_id: int) -> dict[str, Any]:
        version = self.create_version(
            db,
            kind="config",
            payload=AIControlVersionCreate(module=payload.module, payload=payload.payload),
            actor_user_id=actor_user_id,
        )
        self.validate_version(db, version_id=version["id"], actor_user_id=actor_user_id)
        return self.publish_version(db, version_id=version["id"], actor_user_id=actor_user_id)

    def get_version(self, db: Session, *, version_id: int) -> dict[str, Any]:
        row = db.execute(select(ai_control_versions).where(ai_control_versions.c.id == version_id)).mappings().fetchone()
        if row is None:
            raise ValueError("AI control version not found.")
        return self._decode_version(dict(row))

    def validate_version(self, db: Session, *, version_id: int, actor_user_id: int) -> dict[str, Any]:
        version = self.get_version(db, version_id=version_id)
        report = self._validate_payload(version["kind"], version["payload"])
        status = "validated" if report["passed"] else "draft"
        db.execute(
            update(ai_control_versions)
            .where(ai_control_versions.c.id == version_id)
            .values(status=status, validation_report_json=dumps_json(report))
        )
        self._audit(db, actor_user_id=actor_user_id, action=f"ai.{version['kind']}.validate", target_id=str(version_id), after=report)
        db.commit()
        return self.get_version(db, version_id=version_id)

    def publish_version(self, db: Session, *, version_id: int, actor_user_id: int) -> dict[str, Any]:
        version = self.get_version(db, version_id=version_id)
        report = version.get("validation_report") or self._validate_payload(version["kind"], version["payload"])
        if not report.get("passed"):
            raise ValueError("Cannot publish an AI control version that failed validation.")
        db.execute(
            update(ai_control_versions)
            .where(
                ai_control_versions.c.kind == version["kind"],
                ai_control_versions.c.module == version["module"],
                ai_control_versions.c.status == "published",
            )
            .values(status="archived")
        )
        db.execute(
            update(ai_control_versions)
            .where(ai_control_versions.c.id == version_id)
            .values(status="published", published_at=datetime.now(timezone.utc), validation_report_json=dumps_json(report))
        )
        self._audit(db, actor_user_id=actor_user_id, action=f"ai.{version['kind']}.publish", target_id=str(version_id), after=version)
        db.commit()
        return self.get_version(db, version_id=version_id)

    def active_config(self, db: Session) -> dict[str, Any]:
        rows = db.execute(
            select(ai_control_versions).where(
                ai_control_versions.c.kind == "config",
                ai_control_versions.c.status == "published",
            )
        ).mappings()
        merged: dict[str, Any] = {}
        for row in rows:
            merged.update(loads_json(row["payload_json"], {}))
        return merged

    def create_feedback(self, db: Session, *, user_id: int | None, payload: AIFeedbackCreate) -> dict[str, Any]:
        result = db.execute(
            insert(ai_feedback_events).values(
                user_id=user_id,
                request_id=payload.request_id,
                session_id=payload.session_id,
                rating=payload.rating,
                issue_tags_json=dumps_json(payload.issue_tags),
                correction_text=payload.correction_text,
                payload_json=dumps_json(payload.payload),
            )
        )
        feedback_id = int(result.inserted_primary_key[0])
        db.commit()
        return self.get_feedback(db, feedback_id=feedback_id)

    def list_feedback(
        self,
        db: Session,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        query = select(ai_feedback_events)
        if date_from:
            query = query.where(ai_feedback_events.c.created_at >= datetime.combine(date_from, time.min))
        if date_to:
            query = query.where(ai_feedback_events.c.created_at <= datetime.combine(date_to, time.max))
        rows = db.execute(query.order_by(ai_feedback_events.c.id.desc())).mappings()
        return [self._decode_feedback(dict(row)) for row in rows]

    def get_feedback(self, db: Session, *, feedback_id: int) -> dict[str, Any]:
        row = db.execute(select(ai_feedback_events).where(ai_feedback_events.c.id == feedback_id)).mappings().fetchone()
        if row is None:
            raise ValueError("AI feedback event not found.")
        return self._decode_feedback(dict(row))

    def delete_version(self, db: Session, *, version_id: int, actor_user_id: int) -> None:
        version = self.get_version(db, version_id=version_id)
        if version["status"] == "published":
            raise ValueError("Cannot delete a published AI control version.")
        db.execute(delete(ai_control_versions).where(ai_control_versions.c.id == version_id))
        self._audit(db, actor_user_id=actor_user_id, action=f"ai.{version['kind']}.delete", target_id=str(version_id), before=version)
        db.commit()

    def _validate_payload(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        issues: list[str] = []
        if kind == "config":
            for key in payload:
                upper_key = str(key).upper()
                if upper_key not in ALLOWED_CONFIG_KEYS:
                    issues.append(f"Unsupported runtime config key: {key}")
                if any(token in upper_key for token in FORBIDDEN_CONFIG_TOKENS):
                    issues.append(f"Secret-like config key is not allowed through API: {key}")
        if kind in {"prompt", "rule"}:
            text = dumps_json(payload).lower()
            for phrase in FORBIDDEN_POLICY_PHRASES:
                if phrase in text:
                    issues.append(f"Unsafe policy override phrase detected: {phrase}")
        return {"passed": not issues, "issues": issues}

    def _decode_version(self, row: dict[str, Any]) -> dict[str, Any]:
        row["payload"] = loads_json(row.pop("payload_json"), {})
        row["validation_report"] = loads_json(row.pop("validation_report_json"), None)
        return row

    def _decode_feedback(self, row: dict[str, Any]) -> dict[str, Any]:
        row["issue_tags"] = loads_json(row.pop("issue_tags_json"), [])
        row["payload"] = loads_json(row.pop("payload_json"), {})
        return row

    def _audit(
        self,
        db: Session,
        *,
        actor_user_id: int | None,
        action: str,
        target_id: str,
        before: Any = None,
        after: Any = None,
    ) -> None:
        db.execute(
            insert(audit_events).values(
                actor_user_id=actor_user_id,
                action=action,
                target_type="ai_control",
                target_id=target_id,
                before_json=dumps_json(before) if before is not None else None,
                after_json=dumps_json(after) if after is not None else None,
            )
        )

    def _new_version(self) -> str:
        return datetime.now(timezone.utc).strftime("v%Y%m%d%H%M%S%f")


ai_control_service = AIControlService()
