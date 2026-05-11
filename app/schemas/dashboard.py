from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DashboardMacros(BaseModel):
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0


class DashboardOverviewResponse(BaseModel):
    greeting_name: str
    goal_label: str
    weekly_progress: float = 0.0
    calories_consumed: float = 0.0
    calories_target: float = 0.0
    calories_remaining: float = 0.0
    macros: DashboardMacros = Field(default_factory=DashboardMacros)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    bmi: Optional[float] = None
    weight_kg: Optional[float] = None
    bmr: Optional[float] = None
    trend_points: List[Dict[str, Any]] = Field(default_factory=list)
    recent_plans: List[Dict[str, Any]] = Field(default_factory=list)
    profile_completed: bool = False
