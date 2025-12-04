# app/api/v3/auth.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_user_permissions, get_current_user
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models.schemas import Token, UserLogin, UserResponse
from sqlalchemy import text
from fastapi import HTTPException

router = APIRouter()

# Schema response mới cho V3 (Kèm permissions)
class LoginResponseV3(Token):
    permissions: list[str]

@router.post("/login", response_model=LoginResponseV3)
async def login_v3(user_data: UserLogin, db: Session = Depends(get_db)):
    # 1. Logic check pass (Giống hệt V2)
    user = db.execute(text("SELECT * FROM users WHERE username = :u"), {"u": user_data.username}).fetchone()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(401, "Sai tài khoản/mật khẩu")

    # 2. Logic Token (Giống hệt V2)
    access_token = create_access_token(data={"sub": user.username, "id": user.id})
    
    # 3. [MỚI] Lấy danh sách quyền động
    permissions = get_user_permissions(user.id, db)
    
    return {
        "access_token": access_token,
        "refresh_token": "...", # Logic tạo refresh như cũ
        "token_type": "bearer",
        "permissions": list(permissions) # Trả về để Frontend vẽ menu
    }

@router.get("/me")
async def read_users_me_v3(
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # API /me của V3 trả về thêm permissions
    perms = get_user_permissions(current_user.id, db)
    return {
        **current_user._mapping, # Convert row to dict
        "permissions": list(perms)
    }