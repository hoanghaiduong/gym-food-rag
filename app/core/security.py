from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# Cấu hình Hash mật khẩu
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Export hằng số để Router V3 import được
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

import secrets

# Hàm tạo Access Token (Ngắn hạn - 30p)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# Hàm tạo Refresh Token (Opaque - Random String)
def create_refresh_token(expires_delta: Optional[timedelta] = None):
    """
    Tạo Opaque Refresh Token (Chuỗi ngẫu nhiên không chứa thông tin user).
    Truncate về 64 ký tự URL-safe.
    Return: (token_str, expires_at_datetime)
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Tạo chuỗi ngẫu nhiên bảo mật cao
    token = secrets.token_urlsafe(64) 
    return token, expire

def create_reset_token(email: str):
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {
        "sub": email, 
        "type": "reset",  # Đánh dấu đây là token reset, không phải login
        "exp": expire
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# ==========================================
# BỔ SUNG CHO V3: Hàm xác thực Token
# ==========================================
def verify_token(token: str, expected_type: str = "access") -> Optional[dict]:
    """
    Giải mã token và kiểm tra loại token (access/refresh/reset)
    Trả về payload nếu hợp lệ, None nếu lỗi
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Kiểm tra loại token có khớp không (VD: không thể dùng refresh token để gọi API access)
        token_type = payload.get("type")
        if token_type != expected_type:
            return None
            
        return payload
    except JWTError:
        return None