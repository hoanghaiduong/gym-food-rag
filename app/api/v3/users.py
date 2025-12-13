from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, insert, delete
from typing import List

from app.api.deps import get_db, get_current_admin
from app.db.tables import user_roles
from app.models.schemas import UserRoleUpdate, UserResponse

router = APIRouter()

# Schema trả về user kèm roles
class UserWithRoles(UserResponse):
    roles: List[str]

@router.get("/", response_model=List[UserWithRoles])
async def list_users_v3(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Lấy danh sách user kèm role hiện tại"""
    users = db.execute(text("SELECT * FROM users")).mappings().all()
    
    result = []
    for u in users:
        # Lấy tên các role của user này
        role_names = db.execute(text("""
            SELECT r.name FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = :uid
        """), {"uid": u.id}).scalars().all()
        
        # Convert role string cũ sang list nếu cần (backward compatibility)
        # Ở V3 ta ưu tiên bảng user_roles
        roles_display = list(role_names)
        if not roles_display and u.role: # Fallback nếu user cũ chưa migrate
            roles_display.append(u.role)

        user_dict = dict(u)
        user_dict['roles'] = roles_display
        result.append(user_dict)
        
    return result

@router.post("/{user_id}/assign-roles")
async def assign_roles_to_user(
    user_id: int, 
    data: UserRoleUpdate, 
    db: Session = Depends(get_db), 
    admin=Depends(get_current_admin)
):
    """
    Gán danh sách Role ID cho một User.
    Ví dụ: User A -> [1 (Admin), 3 (Editor)]
    """
    try:
        # 1. Xóa hết role cũ trong bảng liên kết
        db.execute(delete(user_roles).where(user_roles.c.user_id == user_id))
        
        # 2. Thêm role mới
        if data.role_ids:
            values = [{"user_id": user_id, "role_id": rid} for rid in data.role_ids]
            db.execute(insert(user_roles), values)
            
        db.commit()
        return {"status": "success", "message": "Đã cập nhật vai trò cho người dùng."}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Lỗi gán role: {str(e)}")