from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    referral_code: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    phone: Optional[str] = None
    referral_code: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    activity_level: Optional[str] = None
    workouts_per_week: Optional[int] = None
    workout_minutes: Optional[int] = None
    training_types: Optional[str] = None
    dietary_preference: Optional[str] = None
    allergies: Optional[str] = None
    disliked_foods: Optional[str] = None
    favorite_meals: Optional[str] = None
    avoid_meals: Optional[str] = None
    medical_conditions: Optional[str] = None
    target_goal: Optional[str] = None
    class Config:
        from_attributes = True

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class OtpRequest(BaseModel):
    target: str = Field(min_length=3, max_length=255)
    channel: Literal["email", "sms"]
    purpose: Literal["register", "reset_password"]


class OtpRequestResponse(BaseModel):
    otp_request_id: str
    channel: str
    target: str
    expires_in_seconds: int
    cooldown_seconds: int
    dev_code: Optional[str] = None


class OtpVerifyRequest(BaseModel):
    otp_request_id: str
    code: str = Field(min_length=6, max_length=6)


class OtpVerifyResponse(BaseModel):
    verification_token: str
    expires_in_seconds: int


class PasswordResetWithOtpRequest(BaseModel):
    verification_token: str
    new_password: str = Field(min_length=6, max_length=128)
