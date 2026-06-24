from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MealLogSource = Literal["manual", "recommendation", "imported"]


class MealLogItemBase(BaseModel):
    entity_id: Optional[str] = None
    food_id: Optional[str] = None
    display_name: str = Field(min_length=1, max_length=255)
    grams: float = Field(ge=0)
    energy_kcal: float = Field(default=0.0, ge=0)
    protein_g: float = Field(default=0.0, ge=0)
    carbs_g: float = Field(default=0.0, ge=0)
    fat_g: float = Field(default=0.0, ge=0)


class MealLogItemCreate(MealLogItemBase):
    pass


class MealLogItemResponse(MealLogItemBase):
    id: int


class MealLogCreate(BaseModel):
    logged_at: datetime
    meal_name: str = Field(min_length=1, max_length=100)
    source: MealLogSource = "manual"
    notes: Optional[str] = None
    items: List[MealLogItemCreate] = Field(min_length=1)


class MealLogUpdate(BaseModel):
    logged_at: Optional[datetime] = None
    meal_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    source: Optional[MealLogSource] = None
    notes: Optional[str] = None
    items: Optional[List[MealLogItemCreate]] = Field(default=None, min_length=1)


class MealLogResponse(BaseModel):
    id: int
    user_id: int
    logged_at: datetime
    meal_name: str
    source: str
    energy_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    notes: Optional[str] = None
    items: List[MealLogItemResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MealLogSummaryResponse(BaseModel):
    log_count: int
    item_count: int
    energy_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
