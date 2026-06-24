from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


WorkoutIntensity = Literal["low", "moderate", "high"]


class WorkoutExerciseBase(BaseModel):
    exercise_name: str = Field(min_length=1, max_length=255)
    sets: Optional[int] = Field(default=None, ge=0, le=100)
    reps: Optional[str] = Field(default=None, max_length=50)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=600)
    rest_seconds: Optional[int] = Field(default=None, ge=0, le=3600)
    notes: Optional[str] = None


class WorkoutExerciseCreate(WorkoutExerciseBase):
    pass


class WorkoutExerciseResponse(WorkoutExerciseBase):
    id: int


class WorkoutLogCreate(BaseModel):
    logged_at: datetime
    workout_type: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(ge=0, le=600)
    intensity: WorkoutIntensity = "moderate"
    calories_estimated: float = Field(default=0.0, ge=0)
    notes: Optional[str] = None
    exercises: List[WorkoutExerciseCreate] = Field(default_factory=list)


class WorkoutLogUpdate(BaseModel):
    logged_at: Optional[datetime] = None
    workout_type: Optional[str] = Field(default=None, min_length=1, max_length=100)
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=600)
    intensity: Optional[WorkoutIntensity] = None
    calories_estimated: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None
    exercises: Optional[List[WorkoutExerciseCreate]] = None


class WorkoutLogResponse(BaseModel):
    id: int
    user_id: int
    logged_at: datetime
    workout_type: str
    duration_minutes: int
    intensity: str
    calories_estimated: float
    notes: Optional[str] = None
    exercises: List[WorkoutExerciseResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkoutLogSummaryResponse(BaseModel):
    log_count: int
    exercise_count: int
    duration_minutes: int
    calories_estimated: float
