from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NutritionIntentHardConstraints(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dietary_preference: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    must_avoid: List[str] = Field(default_factory=list)


class NutritionIntentSoftPreferences(BaseModel):
    model_config = ConfigDict(extra="ignore")

    must_include: List[str] = Field(default_factory=list)
    preferred_foods: List[str] = Field(default_factory=list)
    disliked_foods: List[str] = Field(default_factory=list)
    cooking_complexity: Optional[str] = None
    budget_level: Optional[str] = None
    meal_style: Optional[str] = None


class NutritionIntentMealPreferences(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meal_count: Optional[int] = Field(default=None, ge=3, le=5)
    pre_workout_meal: bool = False
    post_workout_meal: bool = False
    late_dinner: bool = False
    satiety_preference: Optional[str] = None


class NutritionIntent(BaseModel):
    model_config = ConfigDict(extra="allow")

    goal_raw_semantic: Optional[str] = None
    goal_normalized_internal: Optional[str] = None
    planning_strategy: Optional[str] = None
    goal: Optional[str] = None
    priorities: List[str] = Field(default_factory=list)
    hard_constraints: NutritionIntentHardConstraints = Field(default_factory=NutritionIntentHardConstraints)
    soft_preferences: NutritionIntentSoftPreferences = Field(default_factory=NutritionIntentSoftPreferences)
    meal_preferences: NutritionIntentMealPreferences = Field(default_factory=NutritionIntentMealPreferences)
    notes: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = "profile_request_defaults"
    dietary_override: bool = Field(default=False, description="True if must_include conflicts with dietary_preference")
