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