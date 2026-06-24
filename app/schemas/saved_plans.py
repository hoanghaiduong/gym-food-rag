from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.training import TrainingRecommendationRequest


PlanStatus = Literal["active", "archived", "completed"]
PlanType = Literal["nutrition", "training", "weekly", "monthly"]


class SavedPlanCreate(BaseModel):
    plan_type: PlanType
    title: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: PlanStatus = "active"
    payload: Dict[str, Any]
    source_request: Optional[Dict[str, Any]] = None


class SavedPlanUpdate(BaseModel):
    title: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: Optional[PlanStatus] = None
    payload: Optional[Dict[str, Any]] = None
    source_request: Optional[Dict[str, Any]] = None


class SavedPlanResponse(BaseModel):
    id: int
    user_id: int
    plan_type: str
    title: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    status: str
    payload: Dict[str, Any]
    source_request: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WeeklyPlanGenerateRequest(BaseModel):
    week_start: Optional[date] = None
    title: Optional[str] = None
    include_nutrition: bool = True
    include_training: bool = True
    nutrition_request: Optional[NutritionRecommendationRequest] = None
    training_request: Optional[TrainingRecommendationRequest] = None


class MonthlyPlanGenerateRequest(BaseModel):
    year: int = Field(ge=1900, le=2200)
    month: int = Field(ge=1, le=12)
    title: Optional[str] = None
    include_nutrition: bool = True
    include_training: bool = True
    nutrition_request: Optional[NutritionRecommendationRequest] = None
    training_request: Optional[TrainingRecommendationRequest] = None


class SavedPlanListResponse(BaseModel):
    items: List[SavedPlanResponse]
