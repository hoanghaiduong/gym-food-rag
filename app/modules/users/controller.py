from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, PermissionChecker
from app.modules.users.service import UserService
from app.modules.users.schemas import UserRoleUpdate
from app.core.response import success_response

router = APIRouter()

@router.get("/", summary="List all users with roles")
async def list_users(
    page: int = 1, 
    limit: int = 20, 
    db: Session = Depends(get_db), 
    auth=Depends(PermissionChecker("user.view"))
):
    service = UserService(db)
    users, total = service.get_users_with_roles(page, limit)
    
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    meta = {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }
    
    return success_response(data=users, meta=meta)

@router.post("/{user_id}/assign-roles", summary="Assign roles to user")
async def assign_roles(
    user_id: int, 
    data: UserRoleUpdate, 
    db: Session = Depends(get_db), 
    auth=Depends(PermissionChecker("user.edit"))
):
    service = UserService(db)
    service.assign_roles(user_id, data)
    return success_response(message="User roles updated successfully")
