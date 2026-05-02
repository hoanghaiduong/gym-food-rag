from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, paginated_response, success_response
from app.db.tables import users
from app.modules.users.schemas import (
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserRoleUpdate,
    UserWithRoles,
)
from app.modules.users.service import UserService
from app.services.avatar_service import avatar_storage_service


router = APIRouter()

_PREFERENCE_FIELDS = (
    "language",
    "theme",
    "push_notifications",
    "email_notifications",
    "marketing_emails",
    "biometric_unlock_enabled",
)

_PREFERENCE_DEFAULTS = {
    "language": "vi",
    "theme": "system",
    "push_notifications": False,
    "email_notifications": False,
    "marketing_emails": False,
    "biometric_unlock_enabled": False,
}


def _build_preferences_payload(user_row) -> dict:
    user_data = dict(user_row)
    return {
        field: user_data.get(field)
        if user_data.get(field) is not None
        else _PREFERENCE_DEFAULTS[field]
        for field in _PREFERENCE_FIELDS
    }


@router.get("/", response_model=BaseResponse[list[UserWithRoles]], summary="List all users with roles")
async def list_users(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    auth=Depends(PermissionChecker("user.view")),
):
    service = UserService(db)
    user_rows, total = service.get_users_with_roles(page, limit)
    return paginated_response(
        data=user_rows,
        page=page,
        limit=limit,
        total=total,
        message="Fetched users successfully",
    )


@router.post("/me/avatar", response_model=BaseResponse[dict], summary="Upload my avatar")
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(PermissionChecker("user.profile")),
):
    try:
        avatar_url = await avatar_storage_service.save_user_avatar(
            user_id=int(current_user["id"]),
            file=file,
        )
        db.execute(
            update(users)
            .where(users.c.id == current_user["id"])
            .values(avatar_url=avatar_url)
        )
        db.commit()
        updated_user = db.execute(
            select(users).where(users.c.id == current_user["id"])
        ).mappings().fetchone()
        return success_response(
            data={
                "avatar_url": avatar_url,
                "user": dict(updated_user) if updated_user else None,
            },
            message="Cập nhật ảnh đại diện thành công.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/me/preferences",
    response_model=BaseResponse[UserPreferencesResponse],
    summary="Get my app preferences",
)
async def get_my_preferences(
    current_user=Depends(PermissionChecker("user.profile")),
):
    return success_response(
        data=_build_preferences_payload(current_user),
        message="Lấy cài đặt người dùng thành công.",
    )


@router.put(
    "/me/preferences",
    response_model=BaseResponse[UserPreferencesResponse],
    summary="Update my app preferences",
)
async def update_my_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(PermissionChecker("user.profile")),
):
    update_data = payload.model_dump(exclude_none=True)
    if update_data:
        db.execute(
            update(users)
            .where(users.c.id == current_user["id"])
            .values(**update_data)
        )
        db.commit()
        current_user = db.execute(
            select(users).where(users.c.id == current_user["id"])
        ).mappings().fetchone()
    return success_response(
        data=_build_preferences_payload(current_user),
        message="Cập nhật cài đặt người dùng thành công.",
    )


@router.post(
    "/{user_id}/assign-roles",
    response_model=BaseResponse[dict],
    summary="Assign roles to user",
)
async def assign_roles(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    auth=Depends(PermissionChecker("user.edit")),
):
    service = UserService(db)
    service.assign_roles(user_id, data)
    return success_response(message="User roles updated successfully")
