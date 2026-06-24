from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
TrainingGoal = Literal["gain_muscle", "lose_weight", "maintain", "endurance", "mobility"]
TrainingIntensity = Literal["low", "moderate", "high"]


class TrainingRecommendationRequest(BaseModel):
    goal: Optional[TrainingGoal] = None
    experience_level: ExperienceLevel = "beginner"
    workouts_per_week: Optional[int] = Field(default=None, ge=1, le=7)
    workout_minutes: Optional[int] = Field(default=None, ge=15, le=180)
    training_types: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    include_nutrition_timing: bool = True


class TrainingOptionItem(BaseModel):
    value: str
    label: str
    backend_value: Optional[str] = None


class TrainingOptionsResponse(BaseModel):
    goals: List[TrainingOptionItem]
    experience_levels: List[TrainingOptionItem]
    training_types: List[TrainingOptionItem]
    equipment: List[TrainingOptionItem]


class TrainingExercise(BaseModel):
    name: str
    category: str
    sets: Optional[int] = None
    reps: Optional[str] = None
    duration_minutes: Optional[int] = None
    intensity: TrainingIntensity
    rest_seconds: int
    instructions: List[str] = Field(default_factory=list)


class TrainingDayPlan(BaseModel):
    day_index: int
    title: str
    focus: str
    estimated_minutes: int
    warmup: List[str]
    exercises: List[TrainingExercise]
    cooldown: List[str]
    notes: List[str] = Field(default_factory=list)


class TrainingValidationIssue(BaseModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    details: Optional[Dict[str, Any]] = None


class TrainingValidationReport(BaseModel):
    passed: bool
    issues: List[TrainingValidationIssue] = Field(default_factory=list)


class TrainingRecommendationResponse(BaseModel):
    engine: Dict[str, str]
    profile_summary: Dict[str, Any]
    goal: TrainingGoal
    weekly_frequency: int
    session_minutes: int
    intensity: TrainingIntensity
    schedule: List[TrainingDayPlan]
    progression: List[str]
    safety_notes: List[str]
    nutrition_alignment: List[str]
    validation: TrainingValidationReport
