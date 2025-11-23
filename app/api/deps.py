# app/api/deps.py
import os
from fastapi import Depends, HTTPException, status
from fastapi.params import Header
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import Settings
from app.core.security import SECRET_KEY, ALGORITHM

# Kết nối DB
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL) if DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/auth/login")
async def verify_admin(x_admin_key: str = Header(...)):
    """Kiểm tra quyền Admin bằng header key cứng (Chỉ dùng cho bước Setup)"""
    # Key đang dùng trong hệ thống (đã được setup hoặc mặc định)
    current_key = os.getenv("ADMIN_SECRET_KEY", Settings.ADMIN_SECRET_KEY) 
    
    if x_admin_key != current_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="❌ Sai Admin Key! Không thể tiếp tục Setup."
        )
def get_db():
    if not engine: raise HTTPException(500, "Database not connected")
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- 1. KIỂM TRA ĐĂNG NHẬP (Xác thực) ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Lấy user từ DB
    user = db.execute(text("SELECT * FROM users WHERE username = :u"), {"u": username}).fetchone()
    if user is None: raise credentials_exception
    return user

# --- 2. KIỂM TRA QUYỀN ADMIN (Phân quyền) ---
async def get_current_admin(current_user = Depends(get_current_user)):
    # current_user là 1 row trong DB, truy cập thuộc tính role
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quyền truy cập bị từ chối (Yêu cầu quyền Admin)"
        )
    return current_user