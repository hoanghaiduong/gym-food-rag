from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api.deps import get_db, get_current_admin
from app.models.schemas import UserResponse, UserUpdate

router = APIRouter()

# --- 1. XEM DANH SÁCH NGƯỜI DÙNG ---
@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db), 
    admin_user = Depends(get_current_admin) # Yêu cầu quyền Admin
):
    """Lấy danh sách tất cả người dùng (Chỉ Admin)"""
    # Lấy tất cả user (trừ password_hash và refresh_token)
    sql = text("SELECT id, username, email, role, is_active FROM users")
    users = db.execute(sql).fetchall()
    
    # Chuyển đổi kết quả FetchManyRows sang list of dicts
    user_list = [
        UserResponse(
            id=row[0], 
            username=row[1], 
            email=row[2], 
            role=row[3], 
            is_active=row[4]
        ) for row in users
    ]
    return user_list

# --- 2. XEM CHI TIẾT NGƯỜI DÙNG BẰNG ID ---
@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int, 
    db: Session = Depends(get_db), 
    admin_user = Depends(get_current_admin)
):
    """Xem chi tiết người dùng (Chỉ Admin)"""
    sql = text("SELECT id, username, email, role, is_active FROM users WHERE id = :id")
    user = db.execute(sql, {"id": user_id}).fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserResponse(
        id=user[0], username=user[1], email=user[2], role=user[3], is_active=user[4]
    )

# --- 3. CẬP NHẬT NGƯỜI DÙNG ---
@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int, 
    user_in: UserUpdate, 
    db: Session = Depends(get_db), 
    admin_user = Depends(get_current_admin)
):
    """Cập nhật thông tin người dùng, bao gồm Role và Active Status (Chỉ Admin)"""
    # Xây dựng câu lệnh UPDATE động
    updates = user_in.model_dump(exclude_none=True)
    
    if not updates:
        return await get_user_by_id(user_id, db, admin_user)
        
    # Tạo SET clause cho SQL
    set_clause = ", ".join([f"{key} = :{key}" for key in updates.keys()])
    updates["id"] = user_id

    sql = text(f"UPDATE users SET {set_clause} WHERE id = :id")
    
    # Thực hiện update
    db.execute(sql, updates)
    db.commit()
    
    # Trả về đối tượng sau khi update
    return await get_user_by_id(user_id, db, admin_user)

# --- 4. XÓA NGƯỜI DÙNG ---
@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db), admin_user = Depends(get_current_admin)):
    """Xóa người dùng bằng ID (Chỉ Admin)"""
    
    # Không cho Admin tự xóa chính mình (Chỉ Admin mới có ID < 100 thường là user đầu tiên)
    if user_id == admin_user.id:
         raise HTTPException(status_code=400, detail="Không thể tự xóa tài khoản Admin đang hoạt động.")

    sql = text("DELETE FROM users WHERE id = :id RETURNING id")
    result = db.execute(sql, {"id": user_id})
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.commit()
    return {"status": "success", "message": f"User ID {user_id} deleted."}