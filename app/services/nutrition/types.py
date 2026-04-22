from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class WorkflowTargets:
    daily_calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_targets: list[dict[str, Any]] = field(default_factory=list)
    calorie_tolerance_pct: float = 0.0
    macro_tolerance_pct: float = 0.0


@dataclass(slots=True)
class RetrievalContext:
    goal: str
    planning_strategy: str
    dietary_preference: str
    must_include: list[str] = field(default_factory=list)
    preferred_foods: list[str] = field(default_factory=list)
    excluded_foods: list[str] = field(default_factory=list)
    allergy_tags: list[str] = field(default_factory=list)
    expected_role_tags: list[str] = field(default_factory=list)
    anchor_terms: list[str] = field(default_factory=list)
    protein_anchors: list[str] = field(default_factory=list)
    carb_anchors: list[str] = field(default_factory=list)
    produce_anchors: list[str] = field(default_factory=list)
    balanced_anchors: list[str] = field(default_factory=list)
    post_workout_meal: bool = False
    pre_workout_meal: bool = False
    satiety_preference: Optional[str] = None
    balanced_meal_required: bool = False


@dataclass(slots=True)
class CandidateRealism:
    hard_block: bool
    hard_block_reasons: list[str] = field(default_factory=list)
    discouraged_reasons: list[str] = field(default_factory=list)
    preferred_reasons: list[str] = field(default_factory=list)
    normalized_name: str = ""
    normalized_group: str = ""
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    meal_readiness_tier: str = ""
    consumption_state: str = ""
    final_output_allowed: Optional[bool] = None
    unsafe_output_reason: str = ""
    meal_role_tags: list[str] = field(default_factory=list)
    planner_rank_weight: float = 0.0


@dataclass(slots=True)
class CandidateDiagnostics:
    goal: str
    planning_strategy: str
    candidate_count: int
    role_counts: dict[str, int] = field(default_factory=dict)
    must_include_hits: dict[str, bool] = field(default_factory=dict)
    preferred_food_hits: dict[str, bool] = field(default_factory=dict)
    top_candidates: list[str] = field(default_factory=list)
    target_calories: Optional[float] = None
    intent_summary: Optional[dict[str, Any]] = None


@dataclass(slots=True)
class MealBlueprint:
    meal_name: str
    explanation: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    attempt: int = 0
    totals: dict[str, Any] = field(default_factory=dict)
    calorie_error_kcal: float = 0.0
    calorie_error_pct: float = 0.0
    macro_deviation_pct: float = 0.0
    macro_errors_pct: dict[str, float] = field(default_factory=dict)
    macro_error: bool = False
    meal_realism_error: bool = False
    safety_error: bool = False
    unsafe_raw_output_count: int = 0
    unsafe_label_count: int = 0
    substituted_to_safe_variant_count: int = 0
    violation_rate: float = 0.0
    issues: list[dict[str, Any]] = field(default_factory=list)
    checks_failed: int = 0
    checks_total: int = 0
