from __future__ import annotations

from typing import Any, TypedDict

from app.schemas.nutrition import NutritionAgentRecommendationRequest, NutritionRecommendationRequest


class NutritionAgentTraceStep(TypedDict, total=False):
    step: str
    status: str
    meta: dict[str, Any]


class NutritionAgentState(TypedDict, total=False):
    session_id: str
    current_user: dict[str, Any]
    agent_request: NutritionAgentRecommendationRequest
    core_request: NutritionRecommendationRequest
    recommendation: dict[str, Any]
    clarification: dict[str, Any] | None
    validation_passed: bool
    status: str
    answer: str
    error: str
    orchestration_trace: list[NutritionAgentTraceStep]
