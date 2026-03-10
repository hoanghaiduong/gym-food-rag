from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, insert, select, delete, update, func
from typing import List

from app.api.deps import get_db, PermissionChecker
from app.core.response import BaseResponse, success_response
from app.db.tables import roles, permissions, role_permissions
from app.schemas import RoleCreate, RoleResponse, PermissionCreate, RoleUpdate, PermissionBase

router = APIRouter()

# ==========================================
# 1. QUẢN LÝ PERMISSIONS (Quyền hạn)
# ==========================================
# ==========================================
# 1. QUẢN LÝ PERMISSIONS (Quyền hạn)
# ==========================================
# ==========================================
# 1. QUẢN LÝ PERMISSIONS (Quyền hạn)
# ==========================================
@router.get("/permissions", response_model=BaseResponse[List[PermissionBase]])
async def list_permissions(
    page: int = 1, 
    limit: int = 20, 
    db: Session = Depends(get_db), 
    auth=Depends(PermissionChecker("system.config"))
):
    skip = (page - 1) * limit
    
    # Count Total
    total = db.scalar(select(func.count()).select_from(permissions))
    
    # Fetch Data
    result = db.execute(select(permissions).offset(skip).limit(limit)).mappings().all()
    
    # Meta
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    meta = {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }
    
    return success_response(data=result, message="Lấy danh sách quyền thành công", meta=meta)

@router.post("/permissions", response_model=BaseResponse[PermissionBase])
async def create_permission(perm: PermissionCreate, db: Session = Depends(get_db), auth=Depends(PermissionChecker("system.config"))):
    try:
        stmt = insert(permissions).values(
            slug=perm.slug, name=perm.name, description=perm.description
        ).returning(permissions)
        result = db.execute(stmt).mappings().fetchone()
        db.commit()
        return success_response(data=result, message="Tạo quyền thành công")
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Lỗi tạo quyền (có thể trùng slug): {str(e)}")

# ==========================================
# 2. QUẢN LÝ ROLES (Vai trò)
# ==========================================
@router.get("/roles", response_model=BaseResponse[List[RoleResponse]])
async def list_roles(
    page: int = 1, 
    limit: int = 20, 
    db: Session = Depends(get_db), 
    auth=Depends(PermissionChecker("system.config"))
):
    """Lấy danh sách Role kèm theo các quyền của nó"""
    skip = (page - 1) * limit
    
    # Count Total
    total = db.scalar(select(func.count()).select_from(roles))
    
    # Fetch Roles
    roles_list = db.execute(select(roles).offset(skip).limit(limit)).mappings().all()
    
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
    
    # Meta
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    meta = {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }
    
    return success_response(data=response, message="Lấy danh sách vai trò thành công", meta=meta)

@router.post("/roles", response_model=BaseResponse[RoleResponse])
async def create_role(role: RoleCreate, db: Session = Depends(get_db), auth=Depends(PermissionChecker("system.config"))):
    try:
        # 1. Tạo Role
        stmt = insert(roles).values(name=role.name, description=role.description).returning(roles)
        new_role = db.execute(stmt).mappings().fetchone()
        db.commit()
        
        data = {**new_role, "permissions": []}
        return success_response(data=data, message="Tạo vai trò thành công")
    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Lỗi tạo role: {str(e)}")

@router.put("/roles/{role_id}", response_model=BaseResponse)
async def update_role_permissions(
    role_id: int, 
    data: RoleUpdate, 
    db: Session = Depends(get_db), 
    auth=Depends(PermissionChecker("system.config"))
):
    """Cập nhật Role và danh sách quyền (Permissions)"""
    
    # 1. Update thông tin cơ bản (Name, Description)
    # exclude_unset=True: Chỉ lấy các trường có trong JSON gửi lên (bỏ qua các trường null mặc định)
    # exclude={"permissions"}: Tách riêng permissions ra xử lý sau
    update_data = data.model_dump(exclude_unset=True, exclude={"permissions"})
    
    if update_data:
        db.execute(
            update(roles)
            .where(roles.c.id == role_id)
            .values(**update_data)
        )
    
    # 2. Update Permissions (Chỉ chạy nếu người dùng có gửi trường permissions)
    if data.permissions is not None:
        # Xóa hết quyền cũ
        db.execute(delete(role_permissions).where(role_permissions.c.role_id == role_id))
        
        if data.permissions:
            # Tìm ID của các slug quyền gửi lên
            perm_ids = db.execute(
                select(permissions.c.id).where(permissions.c.slug.in_(data.permissions))
            ).scalars().all()
            
            if perm_ids:
                values = [{"role_id": role_id, "permission_id": pid} for pid in perm_ids]
                db.execute(insert(role_permissions), values)
    
    db.commit()
    return success_response(data=None, message="Cập nhật vai trò thành công")