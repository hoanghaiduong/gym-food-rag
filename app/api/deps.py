import os
from typing import Generator, Set
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.models.schemas import TokenData

# Cấu hình DB
db_url = getattr(settings, "DATABASE_URL", None)
engine = None
if db_url:
    engine = create_engine(
        db_url,
        connect_args={"connect_timeout": 1}, 
        pool_size=10, 
        max_overflow=20,
        pool_pre_ping=True
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
security = HTTPBearer()

def get_db() -> Generator:
    if not engine:
        raise HTTPException(500, "Database URL chưa được cấu hình.")
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- 1. XÁC THỰC (AUTHENTICATION) ---
async def get_current_user(token_obj: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn.",
    )
    
    try:
        token = token_obj.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None: raise auth_error
    except JWTError:
        raise auth_error

    # Lấy user (Mapping)
    result = db.execute(
        text("SELECT * FROM users WHERE username = :u"), 
        {"u": username}
    ).mappings().fetchone()

    if result is None: raise auth_error
    if not result['is_active']: raise HTTPException(403, "Tài khoản bị khóa.")
        
    return result

# --- 2. PHÂN QUYỀN (AUTHORIZATION - RBAC) ---

def get_user_permissions(user_id: int, db: Session) -> Set[str]:
    """
    Lấy tất cả quyền của user từ các role họ sở hữu.
    """
    query = text("""
        SELECT DISTINCT p.slug
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN user_roles ur ON rp.role_id = ur.role_id
        WHERE ur.user_id = :uid
    """)
    result = db.execute(query, {"uid": user_id}).fetchall()
    return {row[0] for row in result}

class PermissionChecker:
    """
    Dependency để kiểm tra quyền cụ thể (VD: 'food.create')
    """
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(self, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
        # 1. Lấy quyền từ bảng RBAC mới
        perms = get_user_permissions(current_user['id'], db)
        
        # 2. [QUAN TRỌNG] Backward Compatibility (Hỗ trợ admin cũ chưa migrate)
        # Nếu user có role='admin' ở bảng users cũ -> Tự động cấp full quyền
        if current_user['role'] == 'admin':
            return current_user

        # 3. Kiểm tra quyền
        if self.required_permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bạn thiếu quyền: '{self.required_permission}'"
            )
        return current_user

# --- 3. ADMIN CHECKER (Legacy - Giữ lại để không sửa code cũ quá nhiều) ---
async def get_current_admin(current_user = Depends(get_current_user)):
    if current_user['role'] != "admin":
        raise HTTPException(403, "Yêu cầu quyền Admin.")
    return current_user

# --- 4. SETUP AUTH ---
async def verify_admin(x_admin_key: str = Header(..., description="Admin Setup Key")):
    current_key = os.getenv("ADMIN_SECRET_KEY", settings.ADMIN_SECRET_KEY)
    if x_admin_key != current_key:
        raise HTTPException(403, "Sai Setup Key.")
    return True