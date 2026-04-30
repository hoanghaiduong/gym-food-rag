from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.schemas.nutrition import NutritionRecommendationRequest


class RecommendNutritionPlanToolInput(BaseModel):
    current_user: dict[str, Any] = Field(..., description="Authenticated user/profile payload.")
    request: dict[str, Any] = Field(..., description="NutritionRecommendationRequest-compatible payload.")


def _coerce_core_request(request: NutritionRecommendationRequest | dict[str, Any]) -> NutritionRecommendationRequest:
    if isinstance(request, NutritionRecommendationRequest):
        return NutritionRecommendationRequest(**request.model_dump())
    return NutritionRecommendationRequest(**dict(request))


class NutritionCoreRecommendationTool:
    name = "recommend_nutrition_plan_tool"

    def __init__(self, workflow: Any | None = None):
        self._workflow = workflow

    @property
    def workflow(self) -> Any:
        if self._workflow is None:
            from app.services.nutrition_workflow_service import nutrition_workflow_service

            self._workflow = nutrition_workflow_service
        return self._workflow

    def run(
        self,
        current_user: dict[str, Any],
        request: NutritionRecommendationRequest | dict[str, Any],
    ) -> dict[str, Any]:
        core_request = _coerce_core_request(request)
        return self.workflow.run_main_flow(dict(current_user), core_request)

    def as_langchain_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            name=self.name,
            description=(
                "Generate a validated nutrition recommendation by delegating to "
                "NutritionWorkflowService. This is the only tool allowed to create "
                "final meal-plan decisions."
            ),
            args_schema=RecommendNutritionPlanToolInput,
            func=self.run,
        )


core_recommendation_tool = NutritionCoreRecommendationTool()
recommend_nutrition_plan_tool = core_recommendation_tool.as_langchain_tool()


__all__ = [
    "NutritionCoreRecommendationTool",
    "RecommendNutritionPlanToolInput",
    "core_recommendation_tool",
    "recommend_nutrition_plan_tool",
]
