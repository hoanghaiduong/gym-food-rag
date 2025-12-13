from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = []

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    id: int
    role: str 
    content: str
    created_at: datetime
    class Config:
        from_attributes = True

class ChatHistoryItem(BaseModel):
    id: int
    question: str
    answer: str
    sources: Optional[str] = None
    created_at: datetime
    user_id: int
    session_id: str
    class Config:
        from_attributes = True

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