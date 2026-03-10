from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, insert, select, update,or_
from datetime import timedelta
from typing import List, Optional

# Import Dependencies & Security
from app.api.deps import get_db, get_current_user, get_user_permissions
from app.core.security import (
    create_access_token, 
    create_refresh_token, 
    verify_password, 
    get_password_hash,
    verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# Import Tables & Schemas
from app.db.tables import users, roles, user_roles
from app.schemas import (
    Token, UserLogin, UserCreate, UserResponse, 
    RefreshTokenRequest
)
from pydantic import BaseModel

# Import Global Response Helper (Đảm bảo bạn đã tạo file app/core/response.py)
from app.core.response import BaseResponse, success_response

router = APIRouter()

# ==========================================
# DATA SCHEMAS (Cấu trúc dữ liệu bên trong 'data')
# ==========================================
class LoginData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    permissions: List[str]

class UserData(UserResponse):
    permissions: List[str]

# ==========================================
# 1. REGISTER (ĐĂNG KÝ)
# ==========================================
@router.post("/register", response_model=BaseResponse[UserResponse])
async def register_v3(user_data: UserCreate, db: Session = Depends(get_db)):
    # 1. Check user tồn tại
    existing_user = db.execute(
        select(users).where((users.c.email == user_data.email) | (users.c.username == user_data.username))
    ).fetchone()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Email hoặc Username đã tồn tại")

    # 2. Tạo User (Hash pass & Insert)
    hashed_password = get_password_hash(user_data.password)
    
    try:
        stmt = insert(users).values(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            full_name=user_data.full_name,
            is_active=True
           
        ).returning(users)
        
        new_user = db.execute(stmt).mappings().fetchone()
        
        # 3. Gán Role mặc định 'user'
        default_role_id = db.execute(
            select(roles.c.id).where(roles.c.name == 'user') 
        ).scalar_one_or_none()

        if default_role_id:
            db.execute(
                insert(user_roles).values(user_id=new_user.id, role_id=default_role_id)
            )
        else:
            # Nếu chưa có role 'user', tạo tạm thời hoặc log warning
            print("WARNING: Role 'user' chưa tồn tại. User mới sẽ không có quyền.")

        db.commit()
        
        # Trả về Global Response
        return success_response(data=new_user, message="Đăng ký thành công")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")

# ==========================================
# 2. LOGIN (ĐĂNG NHẬP)
# ==========================================
@router.post("/login", response_model=BaseResponse[LoginData])
async def login_v3(user_data: UserLogin, db: Session = Depends(get_db)):
    # 1. Tìm user bằng Username HOẶC Email
    # user_data.username là dữ liệu người dùng nhập vào (có thể là tên hoặc email)
    user = db.execute(
        select(users).where(
            or_(
                users.c.username == user_data.username, # So khớp với cột username
                users.c.email == user_data.username     # So khớp với cột email
            )
        )
    ).mappings().fetchone()

    # --- Phần còn lại giữ nguyên ---
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Tạo Tokens
    # Lưu ý: Dù đăng nhập bằng email, token vẫn nên lưu 'sub' là username gốc trong DB để thống nhất
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "id": user.id}, 
        expires_delta=access_token_expires
    )
    
    # [NEW] Tạo Opaque Refresh Token
    refresh_token, refresh_expires_at = create_refresh_token()

    # 3. Update Refresh Token vào DB (Kèm Expiry)
    db.execute(
        update(users).where(users.c.id == user.id).values(
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_expires_at
        )
    )
    db.commit()

    # 4. Lấy Permissions
    perms = get_user_permissions(user.id, db)

    # 5. Trả về kết quả chuẩn
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "permissions": list(perms)
    }
    return success_response(data=data, message="Đăng nhập thành công")
# ==========================================
# 3. GET ME (Lấy thông tin bản thân)
# ==========================================
@router.get("/me", response_model=BaseResponse[UserData])
async def read_users_me_v3(
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Trả về thông tin user hiện tại + danh sách quyền hạn
    """
    # 1. Lấy permissions
    perms = get_user_permissions(current_user.id, db)
    
    # 2. Convert User Object sang Dict
    # FIX LỖI _mapping: Vì current_user là RowMapping (dict-like), ta chỉ cần ép kiểu dict()
    try:
        user_dict = dict(current_user)
    except (TypeError, ValueError):
        # Fallback nếu current_user là Pydantic model hoặc object khác
        user_dict = {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at
        }

    # 3. Gắn thêm permissions
    user_dict["permissions"] = list(perms)
    
    return success_response(data=user_dict, message="Lấy thông tin thành công")

# ==========================================
# 4. REFRESH TOKEN
# ==========================================
# ==========================================
# 4. REFRESH TOKEN
# ==========================================
@router.post("/refresh", response_model=BaseResponse[Token])
async def refresh_token_v3(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh Access Token bằng Opaque Refresh Token (Stateful).
    """
    token = request.refresh_token
    
    # 1. Tìm User sở hữu token này
    user = db.execute(select(users).where(users.c.refresh_token == token)).mappings().fetchone()
    
    # 2. Validate
    if not user:
         raise HTTPException(status_code=401, detail="Refresh token không hợp lệ (Không tìm thấy).")
         
    # Check Expiration
    from datetime import datetime
    if not user.refresh_token_expires_at or user.refresh_token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token đã hết hạn. Vui lòng đăng nhập lại.")

    # 3. Token Rotation (Bảo mật: Đổi token mới để tránh Replay Attack)
    new_refresh_token, new_expires_at = create_refresh_token()
    
    db.execute(
        update(users).where(users.c.id == user.id).values(
            refresh_token=new_refresh_token,
            refresh_token_expires_at=new_expires_at
        )
    )
    db.commit()

    # 4. Tạo Access Token mới
    access_token = create_access_token(data={"sub": user.username, "id": user.id})
    
    data = {
        "access_token": access_token,
        "refresh_token": new_refresh_token, # Trả về token mới
        "token_type": "bearer"
    }
    return success_response(data=data, message="Làm mới token thành công")

# ==========================================
# 5. LOGOUT (ĐĂNG XUẤT)
# ==========================================
@router.post("/logout", response_model=BaseResponse)
async def logout_v3(
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Đăng xuất người dùng: Xóa Refresh Token trong Database.
    Client cũng cần xóa Access/Refresh Token ở localStorage/Cookies.
    """
    try:
        # Set refresh_token = NULL cho user hiện tại
        db.execute(
            update(users).where(users.c.id == current_user.id).values(
                refresh_token=None,
                refresh_token_expires_at=None
            )
        )
        db.commit()
        
        return success_response(data=None, message="Đăng xuất thành công")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi đăng xuất: {str(e)}")