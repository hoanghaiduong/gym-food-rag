from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from sqlalchemy import desc, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.db.tables import otp_requests, users


logger = logging.getLogger(__name__)


class OtpService:
    def request_otp(self, db: Session, *, target: str, channel: str, purpose: str) -> dict[str, Any]:
        normalized_target = self._normalize_target(target)
        self._enforce_cooldown(db, normalized_target, channel, purpose)

        code = f"{secrets.randbelow(1_000_000):06d}"
        request_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        db.execute(
            insert(otp_requests).values(
                id=request_id,
                target=normalized_target,
                channel=channel,
                purpose=purpose,
                code_hash=get_password_hash(code),
                expires_at=expires_at,
                attempt_count=0,
                created_at=created_at,
            )
        )
        db.commit()

        logger.info(
            "OTP generated | request_id=%s | channel=%s | purpose=%s | target=%s | dev_mode=%s",
            request_id,
            channel,
            purpose,
            normalized_target,
            settings.OTP_DEV_MODE,
        )
        if settings.OTP_DEV_MODE:
            logger.warning("OTP dev code | request_id=%s | code=%s", request_id, code)

        return {
            "otp_request_id": request_id,
            "channel": channel,
            "target": normalized_target,
            "expires_in_seconds": settings.OTP_EXPIRE_MINUTES * 60,
            "cooldown_seconds": settings.OTP_COOLDOWN_SECONDS,
            "dev_code": code if settings.OTP_DEV_MODE else None,
        }

    def verify_otp(self, db: Session, *, otp_request_id: str, code: str) -> dict[str, Any]:
        row = db.execute(
            select(otp_requests).where(otp_requests.c.id == otp_request_id)
        ).mappings().fetchone()
        if not row:
            raise ValueError("OTP request không tồn tại.")
        if row["verified_at"]:
            raise ValueError("OTP đã được xác thực trước đó.")
        if row["expires_at"] < datetime.utcnow():
            raise ValueError("OTP đã hết hạn.")
        if int(row["attempt_count"] or 0) >= settings.OTP_MAX_ATTEMPTS:
            raise ValueError("OTP đã vượt quá số lần thử.")

        if not verify_password(code, row["code_hash"]):
            db.execute(
                update(otp_requests)
                .where(otp_requests.c.id == otp_request_id)
                .values(attempt_count=int(row["attempt_count"] or 0) + 1)
            )
            db.commit()
            raise ValueError("Mã OTP không chính xác.")

        verified_at = datetime.utcnow()
        db.execute(
            update(otp_requests)
            .where(otp_requests.c.id == otp_request_id)
            .values(verified_at=verified_at)
        )
        db.commit()
        token_expires = verified_at + timedelta(minutes=settings.OTP_VERIFICATION_TOKEN_EXPIRE_MINUTES)
        verification_token = jwt.encode(
            {
                "sub": row["target"],
                "type": "otp_verification",
                "purpose": row["purpose"],
                "otp_request_id": otp_request_id,
                "exp": token_expires,
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return {
            "verification_token": verification_token,
            "expires_in_seconds": settings.OTP_VERIFICATION_TOKEN_EXPIRE_MINUTES * 60,
        }

    def reset_password(self, db: Session, *, verification_token: str, new_password: str) -> None:
        payload = self._decode_verification_token(verification_token, expected_purpose="reset_password")
        target = str(payload["sub"])
        user = db.execute(
            select(users).where(or_(users.c.email == target, users.c.phone == target))
        ).mappings().fetchone()
        if not user:
            raise ValueError("Không tìm thấy tài khoản cho OTP này.")

        db.execute(
            update(users)
            .where(users.c.id == user["id"])
            .values(
                password_hash=get_password_hash(new_password),
                refresh_token=None,
                refresh_token_expires_at=None,
            )
        )
        db.commit()

    def _decode_verification_token(self, token: str, *, expected_purpose: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError as exc:
            raise ValueError("Verification token không hợp lệ hoặc đã hết hạn.") from exc
        if payload.get("type") != "otp_verification":
            raise ValueError("Verification token không đúng loại.")
        if payload.get("purpose") != expected_purpose:
            raise ValueError("Verification token không đúng mục đích.")
        return payload

    def _enforce_cooldown(self, db: Session, target: str, channel: str, purpose: str) -> None:
        latest = db.execute(
            select(otp_requests)
            .where(
                otp_requests.c.target == target,
                otp_requests.c.channel == channel,
                otp_requests.c.purpose == purpose,
            )
            .order_by(desc(otp_requests.c.created_at))
            .limit(1)
        ).mappings().fetchone()
        if not latest or not latest["created_at"]:
            return
        elapsed = (datetime.utcnow() - latest["created_at"]).total_seconds()
        if elapsed < settings.OTP_COOLDOWN_SECONDS:
            raise ValueError("Vui lòng chờ trước khi yêu cầu OTP mới.")

    def _normalize_target(self, target: str) -> str:
        return " ".join(str(target or "").strip().lower().split())


otp_service = OtpService()
