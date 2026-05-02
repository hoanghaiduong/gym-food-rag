from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.paths import STORAGE_DIR


class AvatarStorageService:
    _ALLOWED_TYPES = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    async def save_user_avatar(self, *, user_id: int, file: UploadFile) -> str:
        extension = self._validate_content_type(file.content_type)
        content = await file.read()
        self._validate_size(content)

        avatar_dir = STORAGE_DIR / "avatars" / str(user_id)
        avatar_dir.mkdir(parents=True, exist_ok=True)
        self._remove_existing_avatar(avatar_dir)

        filename = f"avatar{extension}"
        target_path = avatar_dir / filename
        target_path.write_bytes(content)
        return f"/assets/avatars/{user_id}/{filename}"

    def _validate_content_type(self, content_type: str | None) -> str:
        extension = self._ALLOWED_TYPES.get(content_type or "")
        if not extension:
            raise ValueError("Ảnh đại diện chỉ hỗ trợ JPEG, PNG hoặc WEBP.")
        return extension

    def _validate_size(self, content: bytes) -> None:
        if not content:
            raise ValueError("File ảnh rỗng.")
        if len(content) > settings.AVATAR_MAX_UPLOAD_BYTES:
            raise ValueError("Ảnh đại diện vượt quá giới hạn 5MB.")

    def _remove_existing_avatar(self, avatar_dir: Path) -> None:
        for existing in avatar_dir.glob("avatar.*"):
            if existing.is_file():
                existing.unlink()


avatar_storage_service = AvatarStorageService()
