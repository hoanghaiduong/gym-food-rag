from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, insert, select, delete, update
from typing import List

from app.api.deps import get_db, get_current_admin  # Chỉ Admin mới được vào đây
from app.db.schemas import roles, permissions, role_permissions
from app.models.schemas import RoleCreate, RoleResponse, PermissionCreate, RoleUpdate, PermissionBase

router = APIRouter()

# ==========================================
# 1. QUẢN LÝ PERMISSIONS (Quyền hạn)
# ==========================================
@router.get("/permissions", response_model=List[PermissionBase])
async def list_permissions(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    result = db.execute(select(permissions)).mappings().all()
    return result

@router.post("/permissions", response_model=PermissionBase)
async def create_permission(perm: PermissionCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        stmt = insert(permissions).values(
            slug=perm.slug, name=perm.name, description=perm.description
        ).returning(permissions)
        result = db.execute(stmt).mappings().fetchone()
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Lỗi tạo quyền (có thể trùng slug): {str(e)}")

# ==========================================
# 2. QUẢN LÝ ROLES (Vai trò)
# ==========================================
@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Lấy danh sách Role kèm theo các quyền của nó"""
    # Lấy tất cả roles
    roles_list = db.execute(select(roles)).mappings().all()
    
    response = []
    for r in roles_list:
        # Lấy permissions của từng role
        perms_query = text("""
            SELECT p.slug FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            WHERE rp.role_id = :rid
        """)
        perms = db.execute(perms_query, {"rid": r.id}).scalars().all()
        
        response.append({**r, "permissions": list(perms)})
    
    return response

@router.post("/roles", response_model=RoleResponse)
async def create_role(role: RoleCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    try:
        # 1. Tạo Role
        stmt = insert(roles).values(name=role.name, description=role.description).returning(roles)
        new_role = db.execute(stmt).mappings().fetchone()
        db.commit()
        
        return {**new_role, "permissions": []}
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Lỗi tạo role: {str(e)}")

@router.put("/roles/{role_id}")
async def update_role_permissions(
    role_id: int, 
    data: RoleUpdate, 
    db: Session = Depends(get_db), 
    admin=Depends(get_current_admin)
):
    """Cập nhật tên Role và danh sách quyền (Permissions) của Role đó"""
    # 1. Update thông tin cơ bản
    if data.name or data.description:
        update_values = {k: v for k, v in data.model_dump(exclude={"permissions"}).items() if v is not None}
        if update_values:
            db.execute(update(roles).where(roles.c.id == role_id).values(**update_values))
    
    # 2. Update Permissions (Nếu có gửi lên)
    if data.permissions is not None:
        # Xóa quyền cũ
        db.execute(delete(role_permissions).where(role_permissions.c.role_id == role_id))
        
        # Thêm quyền mới
        if data.permissions:
            # Tìm ID của các slug quyền gửi lên
            perm_slugs = data.permissions
            perm_ids = db.execute(
                select(permissions.c.id).where(permissions.c.slug.in_(perm_slugs))
            ).scalars().all()
            
            if perm_ids:
                # Insert hàng loạt
                values = [{"role_id": role_id, "permission_id": pid} for pid in perm_ids]
                db.execute(insert(role_permissions), values)
    
    db.commit()
    return {"message": "Cập nhật Role thành công"}