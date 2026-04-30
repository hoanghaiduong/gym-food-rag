from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NutritionProfileUpdate(BaseModel):
    age: Optional[int] = Field(default=None, ge=10, le=100)
    gender: Optional[str] = None
    weight: Optional[float] = Field(default=None, gt=20, lt=400)
    height: Optional[float] = Field(default=None, gt=100, lt=250)
    activity_level: Optional[str] = None
    dietary_preference: Optional[str] = None
    allergies: Optional[str | List[str]] = None
    target_goal: Optional[str] = None


class NutritionProfile(BaseModel):
    user_id: int
    username: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    activity_level: Optional[str] = None
    dietary_preference: Optional[str] = None
    allergies: Optional[str] = None
    target_goal: Optional[str] = None
    allergy_tags: List[str] = Field(default_factory=list)
    goal_raw_semantic: Optional[str] = None
    goal_normalized_internal: Optional[str] = None
    planning_strategy: Optional[str] = None


class NutritionRecommendationRequest(BaseModel):
    instruction: Optional[str] = None
    meal_count: int = Field(default=3, ge=3, le=5)
    top_k: int = Field(default=18, ge=6, le=40)
    max_revision_rounds: int = Field(default=2, ge=0, le=4)
    calorie_tolerance_pct: float = Field(default=0.10, gt=0.0, le=0.30)
    macro_tolerance_pct: float = Field(default=0.15, gt=0.0, le=0.40)
    use_cache: bool = True
    include_debug: bool = False
    excluded_foods: List[str] = Field(default_factory=list)
    must_include: List[str] = Field(default_factory=list)


class NutritionAgentRecommendationRequest(NutritionRecommendationRequest):
    session_id: Optional[str] = None


class RetrievedFood(BaseModel):
    entity_id: str
    food_id: Optional[str] = None
    entity_type: Optional[str] = None
    granularity: Optional[str] = None
    name: str
    name_en: Optional[str] = None
    group_name: Optional[str] = None
    portion_basis: Optional[str] = None
    portion_g: Optional[float] = None
    portion_g_source: Optional[str] = None
    serving_size_confidence: Optional[str] = None
    image_url: Optional[str] = None
    image_source_url: Optional[str] = None
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: Optional[float] = None
    meal_suggestion: Optional[str] = None
    preparation_style: Optional[str] = None
    ingredient_hints: List[str] = Field(default_factory=list)
    meal_readiness_tier: Optional[str] = None
    consumption_state: Optional[str] = None
    final_output_allowed: Optional[bool] = None
    unsafe_output_reason: Optional[str] = None
    safe_display_name: Optional[str] = None
    meal_role_tags: List[str] = Field(default_factory=list)
    planner_rank_weight: Optional[float] = None
    quality_score: Optional[float] = None
    source_url: Optional[str] = None
    provenance: Optional[str] = None
    diet_tags: List[str] = Field(default_factory=list)
    allergen_tags: List[str] = Field(default_factory=list)
    content: Optional[str] = None
    retrieval_score: Optional[float] = None


class NutritionTargets(BaseModel):
    tdee: float
    daily_calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_targets: List[Dict[str, Any]]
    calorie_tolerance_pct: float
    macro_tolerance_pct: float


class StructuredPlanItem(BaseModel):
    entity_id: Optional[str] = None
    food_name: str
    grams: int
    reason: Optional[str] = None


class StructuredMeal(BaseModel):
    meal_name: str
    explanation: str
    items: List[StructuredPlanItem]


class StructuredMealPlan(BaseModel):
    summary: str
    reasoning: List[str] = Field(default_factory=list)
    meals: List[StructuredMeal]


class ResolvedPlanItem(StructuredPlanItem):
    food_id: Optional[str] = None
    source_food_name: Optional[str] = None
    group_name: Optional[str] = None
    image_url: Optional[str] = None
    image_source_url: Optional[str] = None
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    allergen_tags: List[str] = Field(default_factory=list)
    diet_tags: List[str] = Field(default_factory=list)
    meal_readiness_tier: Optional[str] = None
    consumption_state: Optional[str] = None
    final_output_allowed: Optional[bool] = None
    unsafe_output_reason: Optional[str] = None
    safe_display_name: Optional[str] = None
    meal_role_tags: List[str] = Field(default_factory=list)
    planner_rank_weight: Optional[float] = None
    preparation_style: Optional[str] = None
    ingredient_hints: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    substituted_to_safe_variant: bool = False
    substituted_from_entity_id: Optional[str] = None
    substituted_from_name: Optional[str] = None
    resolved: bool = True


class ResolvedMeal(BaseModel):
    meal_name: str
    explanation: str
    items: List[ResolvedPlanItem]
    totals: Dict[str, float]


class PlanTotals(BaseModel):
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0


class ValidationIssue(BaseModel):
    code: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ValidationReport(BaseModel):
    passed: bool
    attempt: int
    totals: PlanTotals
    calorie_error_kcal: float
    calorie_error_pct: float
    macro_deviation_pct: float
    macro_errors_pct: Dict[str, float]
    macro_error: Optional[bool] = None
    meal_realism_error: Optional[bool] = None
    safety_error: Optional[bool] = None
    unsafe_raw_output_count: int = 0
    unsafe_label_count: int = 0
    substituted_to_safe_variant_count: int = 0
    violation_rate: float
    issues: List[ValidationIssue] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    step: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None


class NutritionRecommendationResponse(BaseModel):
    request_id: str
    cached: bool = False
    engine: Dict[str, str]
    profile: NutritionProfile
    targets: NutritionTargets
    plan: StructuredMealPlan
    resolved_meals: List[ResolvedMeal]
    totals: PlanTotals
    validation: ValidationReport
    retrieved_context: List[RetrievedFood]
    grounded_foods: List[RetrievedFood]
    revisions_used: int
    response_time_seconds: float
    workflow_trace: List[WorkflowStep]
    debug: Optional[Dict[str, Any]] = None


class NutritionAgentRecommendationResponse(BaseModel):
    session_id: str
    answer: str
    recommendation: Optional[NutritionRecommendationResponse] = None
    orchestration_trace: List[Dict[str, Any]] = Field(default_factory=list)
    engine: Dict[str, str]
    validation_passed: bool
    status: str


class WorkflowStateResponse(BaseModel):
    request_id: str
    status: str
    payload: Dict[str, Any]


class EvaluationVariantResult(BaseModel):
    name: str
    response_time_seconds: float
    totals: PlanTotals
    calorie_error_kcal: float
    calorie_error_pct: float
    macro_deviation_pct: float
    violation_rate: float
    passed: bool
    notes: List[str] = Field(default_factory=list)


class NutritionEvaluationResponse(BaseModel):
    request_id: str
    created_at: datetime
    profile: NutritionProfile
    targets: NutritionTargets
    variants: List[EvaluationVariantResult]
    best_variant: str
    log_path: str


class WorkflowStatePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    status: str
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    response_excerpt: Optional[Dict[str, Any]] = None
