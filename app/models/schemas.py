from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any

# =================================================================
# 1. AUTHENTICATION & USERS (Xác thực & Người dùng)
# =================================================================

class Token(BaseModel):
    """Token trả về khi đăng nhập thành công"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Dữ liệu giải mã từ Token"""
    username: Optional[str] = None
    user_id: Optional[int] = None

class UserLogin(BaseModel):
    """Input cho API Login"""
    username: str
    password: str

class UserCreate(BaseModel):
    """Input cho API Register"""
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserUpdate(BaseModel):
    """Input cho API Update User"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    """Output thông tin User trả về Client"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    
    # Cho phép đọc từ SQLAlchemy Object
    class Config:
        from_attributes = True

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# =================================================================
# 2. RBAC (Role-Based Access Control) - V3 SYSTEM
# =================================================================

class PermissionOut(BaseModel):
    """Hiển thị quyền hạn"""
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    class Config:
        from_attributes = True

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    """Input tạo Role mới"""
    permissions: List[str] = [] # Danh sách slug (VD: ['food.create'])

class RoleUpdate(BaseModel):
    """Input cập nhật Role"""
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

class RoleResponse(RoleBase):
    """Output hiển thị Role"""
    id: int
    permissions: List[str] = [] # Danh sách slug quyền
    class Config:
        from_attributes = True

class AssignRoleRequest(BaseModel):
    """Input để Gán quyền cho User"""
    user_id: int
    role_name: str

# =================================================================
# 3. E-COMMERCE (Sản phẩm & Đơn hàng) - NEW V4
# =================================================================

class ProductBase(BaseModel):
    name: str
    price: int
    image_url: Optional[str] = None
    description: Optional[str] = None
    category: str = "supplements" # 'supplements' (Kho) hoặc 'fresh_food' (BHX)
    
    # Metadata cho Blockchain & Affiliate
    affiliate_link: Optional[str] = None  # Link BHX (nếu có)
    batch_id: Optional[str] = None        # Mã lô hàng (cho hàng kho)
    audit_id: Optional[str] = None        # Mã kiểm định (cho hàng BHX)

class ProductCreate(ProductBase):
    stock: int = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    stock: Optional[int] = None

class ProductResponse(ProductBase):
    id: int
    stock: int
    created_at: datetime
    class Config:
        from_attributes = True

class OrderRequest(BaseModel):
    """Input tạo đơn hàng (từ AI Agent)"""
    user_id: int
    product_id: int
    quantity: int = 1
    shipping_address: Optional[str] = None
    note: Optional[str] = None

class OrderResponse(BaseModel):
    """Output thông tin đơn hàng"""
    id: int
    total_price: int
    status: str # 'PENDING', 'CONFIRMED', 'SHIPPING', 'COMPLETED'
    created_at: datetime
    class Config:
        from_attributes = True

# =================================================================
# 4. BLOCKCHAIN & AUDIT (Truy xuất nguồn gốc)
# =================================================================

class AuditLogCreate(BaseModel):
    """Input để Admin ghi log kiểm định (Audit)"""
    source_name: str = "Bach Hoa Xanh"
    check_date: str # Format: YYYY-MM-DD
    result: str # VD: "Passed", "Good"
    proof_url: Optional[str] = None
    notes: Optional[str] = None

class BlockchainVerifyResponse(BaseModel):
    """Output khi User kiểm tra nguồn gốc"""
    status: str # 'success', 'not_found', 'fake'
    data: Optional[Dict[str, Any]] = None
    message: str
    timestamp: datetime = datetime.now()

# =================================================================
# 5. CORE CHAT & RAG (Trợ lý ảo)
# =================================================================

class ChatRequest(BaseModel):
    """Input khi User chat"""
    question: str
    session_id: Optional[str] = None # Nếu null -> Tạo session mới
    history: Optional[List[Dict[str, str]]] = [] # Dành cho client muốn tự quản lý context (optional)

class ChatSessionResponse(BaseModel):
    """Hiển thị danh sách hội thoại bên Sidebar"""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    """Hiển thị 1 tin nhắn cụ thể"""
    id: int
    role: str # user/assistant
    content: str
    created_at: datetime
    class Config:
        from_attributes = True

class ChatHistoryItem(BaseModel):
    """Chi tiết lịch sử lưu trong DB"""
    id: int
    question: str
    answer: str
    sources: Optional[str] = None # JSON string
    created_at: datetime
    user_id: int
    session_id: str
    class Config:
        from_attributes = True

class FoodItem(BaseModel):
    """Output cấu trúc dữ liệu dinh dưỡng (RAG)"""
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
# 6. SETUP WIZARD (Cấu hình hệ thống lần đầu)
# =================================================================

class FirstAdminRequest(BaseModel):
    username: str
    email: EmailStr
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