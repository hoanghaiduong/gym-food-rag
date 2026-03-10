from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, paginated_response, success_response
from app.modules.users.schemas import UserRoleUpdate, UserWithRoles
from app.modules.users.service import UserService


router = APIRouter()


@router.get("/", response_model=BaseResponse[list[UserWithRoles]], summary="List all users with roles")
async def list_users(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    auth=Depends(PermissionChecker("user.view")),
):
    service = UserService(db)
    users, total = service.get_users_with_roles(page, limit)
    return paginated_response(
        data=users,
        page=page,
        limit=limit,
        total=total,
        message="Fetched users successfully",
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
