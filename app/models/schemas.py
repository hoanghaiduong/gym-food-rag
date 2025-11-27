from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# =================================================================
# CORE CHAT/RAG SCHEMAS
# =================================================================

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, str]]] = [] 

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] 

class FoodItem(BaseModel):
    name: str
    group: str
    energy_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_suggestion: str
    provenance: Optional[str] = None
    document_content: str 

# =================================================================
# SETUP WIZARD CONFIG SCHEMAS (Step 0-5)
# =================================================================
class FirstAdminRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = "System Administrator"
    
class AdminSetupConfig(BaseModel):
    admin_secret_key: str 

class NetworkConfig(BaseModel):
    api_base_url: str
    websocket_url: str

class DatabaseConfig(BaseModel):
    db_type: str = "PostgreSQL"
    host: str
    port: str
    username: str
    password: str
    db_name: str

class VectorConfig(BaseModel):
    provider: str = "Qdrant"
    host: str
    api_key: Optional[str] = None
    collection_name: str

class LLMConfig(BaseModel):
    provider: str = "Gemini"
    api_key: str
    model_name: str = "gemini-2.5-flash"

class GeneralConfig(BaseModel):
    bot_name: str
    welcome_message: str
    language: str = "Vietnamese"
    
# =================================================================
# AUTHENTICATION & USER MANAGEMENT SCHEMAS (Bổ sung đầy đủ)
# =================================================================

class UserCreate(BaseModel):
    """Schema cho /register"""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    
class UserLogin(BaseModel):
    """Schema cho form đăng nhập (/login)"""
    username: str
    password: str

class UserResponse(BaseModel):
    """Schema trả về thông tin người dùng"""
    id: int
    username: str
    email: str
    role: str
    is_active: bool

class UserUpdate(BaseModel):
    """Schema dùng cho /users/{id} để cập nhật thông tin"""
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None 
    is_active: Optional[bool] = None 

class Token(BaseModel):
    """Schema trả về sau khi Login/Refresh"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    
class RefreshTokenRequest(BaseModel):
    """Schema nhận Refresh Token từ Client"""
    refresh_token: str
    
class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    
class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
    
class ChatHistoryItem(BaseModel):
    id: int
    question: str
    answer: str
    sources: Optional[str] = None # JSON string
    created_at: datetime

    class Config:
        from_attributes = True # Cho phép đọc từ SQLAlchemy Row