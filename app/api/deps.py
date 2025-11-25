import os
from typing import Generator
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer,HTTPBearer,HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.models.schemas import TokenData
from sqlalchemy.exc import OperationalError
# Cấu hình kết nối DB
# Sử dụng getattr để tránh lỗi nếu settings chưa load xong
db_url = getattr(settings, "DATABASE_URL", None)
engine = None
if db_url:
    engine = create_engine(
        db_url,
        connect_args={"connect_timeout": 1}, # Timeout 2s là đủ
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True # Tự động ping lại nếu kết nối rớt
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
security = HTTPBearer()
# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/auth/login")
def get_db() -> Generator:
    if not engine:
        raise HTTPException(500, "Database URL chưa được cấu hình.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# --- 1. XÁC THỰC NGƯỜI DÙNG (AUTHENTICATION) ---
# --- 1. XÁC THỰC NGƯỜI DÙNG ---
async def get_current_user(token_obj: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    # Định nghĩa lỗi chung để tái sử dụng
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn.",
    )
    
    token = token_obj.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None:
            raise auth_error
        
        # Chỉ map dữ liệu, không cần validate lại bằng Pydantic nếu không cần thiết
        # để tăng tốc độ
        
    except JWTError:
        raise auth_error

    # Query DB
    # Không cần try-except ở đây nữa, nếu DB lỗi thì Global Handler ở main.py sẽ bắt
    # result = db.execute(
    #     text("SELECT role, is_active FROM users WHERE username = :u"), 
    #     {"u": username}
    # ).mappings().fetchone()
    # Query DB
    # Lấy đủ thông tin để khớp với UserResponse schema
    result = db.execute(
        text("SELECT * FROM users WHERE username = :u"), 
        {"u": username}
    ).mappings().fetchone()

    if result is None:
        raise auth_error # User không tồn tại
    
    if not result['is_active']: 
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa.")
        
    # Trả về object có đủ thông tin cần thiết cho các hàm sau
    # Thêm username vào kết quả trả về để dùng nếu cần
    return result
# --- 2. PHÂN QUYỀN ADMIN (RBAC) ---
async def get_current_admin(current_user = Depends(get_current_user)):
    if current_user['role'] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền quản trị viên (Admin)."
        )
    return current_user

# --- 3. XÁC THỰC SETUP WIZARD ---
async def verify_admin(x_admin_key: str = Header(..., description="Admin Setup Key")):
    current_key = os.getenv("ADMIN_SECRET_KEY", settings.ADMIN_SECRET_KEY)
    if x_admin_key != current_key:
        raise HTTPException(status_code=403, detail="Sai khóa xác thực Setup.")
    return True