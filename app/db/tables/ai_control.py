from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, func

from app.db.base import metadata


ai_control_versions = Table(
    "ai_control_versions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("kind", String(30), nullable=False),
    Column("module", String(100), nullable=False),
    Column("version", String(50), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("status", String(30), nullable=False, default="draft"),
    Column("validation_report_json", Text, nullable=True),
    Column("created_by", Integer, ForeignKey("users.id"), nullable=True),
    Column("published_at", DateTime, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)


ai_feedback_events = Table(
    "ai_feedback_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("request_id", String(100), nullable=True),
    Column("session_id", String(100), nullable=True),
    Column("rating", Integer, nullable=True),
    Column("issue_tags_json", Text, nullable=True),
    Column("correction_text", Text, nullable=True),
    Column("payload_json", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
)


audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("actor_user_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("action", String(100), nullable=False),
    Column("target_type", String(100), nullable=False),
    Column("target_id", String(100), nullable=True),
    Column("before_json", Text, nullable=True),
    Column("after_json", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
)
