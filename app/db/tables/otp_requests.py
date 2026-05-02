from sqlalchemy import Column, DateTime, Integer, String, Table, func

from app.db.base import metadata


otp_requests = Table(
    "otp_requests",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("target", String(255), nullable=False),
    Column("channel", String(20), nullable=False),
    Column("purpose", String(50), nullable=False),
    Column("code_hash", String(255), nullable=False),
    Column("expires_at", DateTime, nullable=False),
    Column("verified_at", DateTime, nullable=True),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("created_at", DateTime, server_default=func.now()),
)
