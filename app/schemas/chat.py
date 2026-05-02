from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list)


class ChatResponseV3(BaseModel):
    answer: str
    session_id: str
    engine: str
    status: str = Field(
        description="answered | use_nutrition_agent | needs_question | fallback"
    )
    context_used: List[str] = Field(default_factory=list)
    suggested_endpoint: Optional[str] = None

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
