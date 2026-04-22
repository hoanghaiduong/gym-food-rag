from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# ==========================================
# 1. AUTH & TOKEN SCHEMAS
# ==========================================
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# ==========================================
# 2. USER CRUD SCHEMAS
# ==========================================
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    activity_level: Optional[str] = None
    dietary_preference: Optional[str] = None
    allergies: Optional[str] = None
    target_goal: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    activity_level: Optional[str] = None
    dietary_preference: Optional[str] = None
    allergies: Optional[str] = None
    target_goal: Optional[str] = None
    
    class Config:
        from_attributes = True

# ==========================================
# 3. PASSWORD RESET SCHEMAS
# ==========================================
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# ==========================================
# 4. RBAC / USER ROLE SCHEMAS (BỔ SUNG)
# ==========================================
class UserRoleUpdate(BaseModel):
    """Schema dùng để gán danh sách Role ID cho User"""
    role_ids: List[int] = []