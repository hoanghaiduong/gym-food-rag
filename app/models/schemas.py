from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Schema cho câu hỏi người dùng gửi lên
class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, str]]] = [] # Lịch sử chat (nếu cần)

# Schema cho dữ liệu nguồn (Món ăn)
class FoodItem(BaseModel):
    name: str
    group: str
    energy_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_suggestion: str
    provenance: Optional[str] = None
    document_content: str # Chuỗi đã template hóa

# Schema cho câu trả lời trả về
class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] # Trả về nguồn tham khảo để người dùng tin tưởng
    
# [THÊM MỚI] Step 0: Admin Creation
class AdminSetupConfig(BaseModel):
    admin_secret_key: str # Người dùng tự nhập mật khẩu quản trị mong muốn
# Schema cho cấu hình mạng (STEP 1)
# Step 1: Network
class NetworkConfig(BaseModel):
    api_base_url: str
    websocket_url: str

# Step 2: Database
class DatabaseConfig(BaseModel):
    db_type: str = "PostgreSQL"
    host: str
    port: str
    username: str
    password: str
    db_name: str

# Step 3: Vector DB
class VectorConfig(BaseModel):
    provider: str = "Qdrant"
    host: str
    api_key: Optional[str] = None
    collection_name: str

# Step 4: LLM
class LLMConfig(BaseModel):
    provider: str = "Gemini"
    api_key: str
    model_name: str = "gemini-1.5-flash"

# Step 5: General
class GeneralConfig(BaseModel):
    bot_name: str
    welcome_message: str
    language: str = "Vietnamese"