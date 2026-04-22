from __future__ import annotations

from typing import Any, TypedDict


class MealTarget(TypedDict):
    meal_name: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class WorkflowTargets(TypedDict):
    tdee: float
    daily_calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meal_targets: list[MealTarget]
    calorie_tolerance_pct: float
    macro_tolerance_pct: float


class CandidateDiagnostics(TypedDict, total=False):
    goal: str
    planning_strategy: str | None
    candidate_count: int
    role_counts: dict[str, int]
    must_include_hits: dict[str, bool]
    preferred_food_hits: dict[str, bool]
    top_candidates: list[str | None]
    target_calories: float | None
    intent_summary: dict[str, Any] | None


class ValidationResult(TypedDict, total=False):
    passed: bool
    attempt: int
    totals: dict[str, float]
    calorie_error_kcal: float
    calorie_error_pct: float
    macro_deviation_pct: float
    macro_errors_pct: dict[str, float]
    macro_error: bool
    meal_realism_error: bool
    safety_error: bool
    unsafe_raw_output_count: int
    unsafe_label_count: int
    substituted_to_safe_variant_count: int
    violation_rate: float
    issues: list[dict[str, Any]]


class GenerationAttempt(TypedDict, total=False):
    attempt: int
    attempt_count: int
    strategy: str
    raw_text: str
    plan_json: dict[str, Any]
    resolved_plan: dict[str, Any]
    validation: ValidationResult
    grounded_foods: list[dict[str, Any]]
    explanation_mode: str
    candidate_diagnostics: CandidateDiagnostics


class WorkflowTraceEntry(TypedDict):
    step: str
    status: str
    started_at: str
    ended_at: str
    meta: dict[str, Any]
