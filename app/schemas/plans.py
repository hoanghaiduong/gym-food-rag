from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel


PlanTimelineStatus = Literal["completed", "active", "upcoming", "insight"]


class WeeklyTimelineItem(BaseModel):
    id: str
    day_label: str
    title: str
    subtitle: str
    status: PlanTimelineStatus


class MonthlyDay(BaseModel):
    day: int
    has_completed_workout: bool
    has_planned_workout: bool
    is_today: bool


class MonthlyProgress(BaseModel):
    workout_completed: int
    workout_target: int
    nutrition_completed: int
    nutrition_target: int


class MonthlySelectedDay(BaseModel):
    date: date
    title: str
    subtitle: str
    calories: float


class MonthlyPlansResponse(BaseModel):
    year: int
    month: int
    days: List[MonthlyDay]
    monthly_progress: MonthlyProgress
    selected_day: Optional[MonthlySelectedDay]
