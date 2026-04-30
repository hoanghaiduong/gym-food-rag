from __future__ import annotations

import uuid
from typing import Any

from app.core.config import settings
from app.schemas.nutrition import NutritionAgentRecommendationRequest, NutritionRecommendationRequest

from .graph import NutritionAgentGraph, build_nutrition_agent_graph


class NutritionAgentService:
    def __init__(self, graph: NutritionAgentGraph | None = None):
        self._graph = graph

    @property
    def graph(self) -> NutritionAgentGraph:
        if self._graph is None:
            self._graph = build_nutrition_agent_graph()
        return self._graph

    def run(
        self,
        current_user: dict[str, Any],
        request: NutritionAgentRecommendationRequest | NutritionRecommendationRequest | dict[str, Any],
    ) -> dict[str, Any]:
        agent_request = self._coerce_agent_request(request)
        session_id = agent_request.session_id or str(uuid.uuid4())
        final_state = self.graph.invoke(
            {
                "session_id": session_id,
                "current_user": dict(current_user),
                "agent_request": agent_request,
                "orchestration_trace": [],
            },
            session_id=session_id,
        )
        validation_passed = bool(final_state.get("validation_passed"))
        return {
            "session_id": session_id,
            "answer": final_state.get("answer") or "",
            "recommendation": final_state.get("recommendation") if validation_passed else None,
            "orchestration_trace": final_state.get("orchestration_trace") or [],
            "engine": self._engine_metadata(),
            "validation_passed": validation_passed,
            "status": final_state.get("status") or "unknown",
        }

    def _coerce_agent_request(
        self,
        request: NutritionAgentRecommendationRequest | NutritionRecommendationRequest | dict[str, Any],
    ) -> NutritionAgentRecommendationRequest:
        if isinstance(request, NutritionAgentRecommendationRequest):
            return request
        if isinstance(request, NutritionRecommendationRequest):
            return NutritionAgentRecommendationRequest(**request.model_dump())
        return NutritionAgentRecommendationRequest(**dict(request))

    def _engine_metadata(self) -> dict[str, str]:
        return {
            "orchestrator": "langgraph",
            "tooling": "langchain_structured_tool",
            "decision_engine": "NutritionWorkflowService",
            "decision_contract": "validated_core_response_only",
            "llm_role": "intent_clarification_and_explanation_only",
            "llm_backend": "ollama",
            "llm_model": settings.nutrition_agent_model,
            "checkpoint_backend": self.graph.checkpoint_backend,
        }


nutrition_agent_service = NutritionAgentService()
