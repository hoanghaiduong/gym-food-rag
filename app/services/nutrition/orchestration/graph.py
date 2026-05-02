from __future__ import annotations

import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.schemas.nutrition import NutritionAgentRecommendationRequest, NutritionRecommendationRequest
from app.services.nutrition_intent_service import nutrition_intent_service

from .explanations import NutritionAgentExplanationBuilder
from .safety_clarification import NutritionAgentSafetyClarificationPolicy
from .state import NutritionAgentState, NutritionAgentTraceStep
from .tools import NutritionCoreRecommendationTool, core_recommendation_tool


class NutritionAgentGraph:
    def __init__(
        self,
        *,
        core_tool: NutritionCoreRecommendationTool | None = None,
        explanation_builder: NutritionAgentExplanationBuilder | None = None,
        intent_parser: Any | None = None,
        safety_clarification_policy: NutritionAgentSafetyClarificationPolicy | None = None,
    ):
        self.core_tool = core_tool or core_recommendation_tool
        self.explanation_builder = explanation_builder or NutritionAgentExplanationBuilder()
        self.intent_parser = intent_parser or nutrition_intent_service
        self.safety_clarification_policy = safety_clarification_policy or NutritionAgentSafetyClarificationPolicy()
        self.checkpoint_backend = "none"
        self.app = self._build_graph()

    def invoke(self, state: NutritionAgentState, *, session_id: str | None = None) -> NutritionAgentState:
        config = {"configurable": {"thread_id": session_id or state.get("session_id") or str(uuid.uuid4())}}
        return self.app.invoke(state, config=config)

    def _build_graph(self):
        workflow = StateGraph(NutritionAgentState)
        workflow.add_node("normalize_request", self._normalize_request)
        workflow.add_node("clarify_intent", self._clarify_intent)
        workflow.add_node("run_core_recommendation", self._run_core_recommendation)
        workflow.add_node("inspect_validation", self._inspect_validation)
        workflow.add_node("generate_explanation", self._generate_explanation)
        workflow.add_node("finalize_response", self._finalize_response)

        workflow.set_entry_point("normalize_request")
        workflow.add_edge("normalize_request", "clarify_intent")
        workflow.add_conditional_edges(
            "clarify_intent",
            self._route_after_clarification,
            {
                "run_core_recommendation": "run_core_recommendation",
                "finalize_response": "finalize_response",
            },
        )
        workflow.add_edge("run_core_recommendation", "inspect_validation")
        workflow.add_edge("inspect_validation", "generate_explanation")
        workflow.add_edge("generate_explanation", "finalize_response")
        workflow.add_edge("finalize_response", END)
        return workflow.compile(checkpointer=self._build_checkpointer())

    def _build_checkpointer(self) -> Any | None:
        if not settings.NUTRITION_AGENT_REDIS_CHECKPOINT:
            return None
        try:
            from langgraph.checkpoint.redis import RedisSaver

            saver = RedisSaver(redis_url=settings.redis_url)
            saver.setup()
        except Exception:
            return None
        self.checkpoint_backend = "redis"
        return saver

    def _normalize_request(self, state: NutritionAgentState) -> dict[str, Any]:
        agent_request = state.get("agent_request")
        if not isinstance(agent_request, NutritionAgentRecommendationRequest):
            agent_request = NutritionAgentRecommendationRequest(**dict(agent_request or {}))
        session_id = state.get("session_id") or agent_request.session_id or str(uuid.uuid4())
        core_payload = agent_request.model_dump(exclude={"session_id"})
        core_request = NutritionRecommendationRequest(**core_payload)
        return {
            "session_id": session_id,
            "agent_request": agent_request,
            "core_request": core_request,
            "status": "normalized",
            "orchestration_trace": self._trace(state, "normalize_request", "completed"),
        }

    def _clarify_intent(self, state: NutritionAgentState) -> dict[str, Any]:
        request = state["core_request"]
        instruction = request.instruction or ""
        safety_clarification = self.safety_clarification_policy.build(state.get("current_user") or {}, request)
        if safety_clarification:
            return {
                "clarification": safety_clarification,
                "status": "needs_clarification",
                "answer": str(safety_clarification.get("question") or ""),
                "orchestration_trace": self._trace(
                    state,
                    "clarify_intent",
                    "needs_clarification",
                    {
                        "reason": safety_clarification.get("reason"),
                        "required_fields": safety_clarification.get("required_fields") or [],
                    },
                ),
            }
        if not instruction.strip():
            return {
                "status": "intent_ready",
                "orchestration_trace": self._trace(state, "clarify_intent", "skipped", {"reason": "empty_instruction"}),
            }
        try:
            clarification = self.intent_parser.get_chat_clarification(state.get("current_user") or {}, instruction)
        except Exception as exc:  # pragma: no cover - defensive fallback for unavailable LLM backends
            return {
                "status": "intent_ready",
                "orchestration_trace": self._trace(
                    state,
                    "clarify_intent",
                    "warning",
                    {"reason": f"clarifier_unavailable: {exc}"},
                ),
            }
        if clarification:
            return {
                "clarification": clarification,
                "status": "needs_clarification",
                "answer": str(clarification.get("question") or ""),
                "orchestration_trace": self._trace(state, "clarify_intent", "needs_clarification"),
            }
        return {
            "status": "intent_ready",
            "orchestration_trace": self._trace(state, "clarify_intent", "completed"),
        }

    def _route_after_clarification(self, state: NutritionAgentState) -> str:
        if state.get("status") == "needs_clarification":
            return "finalize_response"
        return "run_core_recommendation"

    def _run_core_recommendation(self, state: NutritionAgentState) -> dict[str, Any]:
        try:
            recommendation = self.core_tool.run(state.get("current_user") or {}, state["core_request"])
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "orchestration_trace": self._trace(state, "run_core_recommendation", "failed"),
            }
        return {
            "recommendation": recommendation,
            "status": "core_completed",
            "orchestration_trace": self._trace(
                state,
                "run_core_recommendation",
                "completed",
                {"request_id": recommendation.get("request_id")},
            ),
        }

    def _inspect_validation(self, state: NutritionAgentState) -> dict[str, Any]:
        recommendation = state.get("recommendation") or {}
        validation = recommendation.get("validation") or {}
        validation_passed = bool(validation.get("passed")) and not self._has_unsafe_output(recommendation)
        status = "validated" if validation_passed else "needs_revision"
        return {
            "status": status,
            "validation_passed": validation_passed,
            "orchestration_trace": self._trace(
                state,
                "inspect_validation",
                "completed",
                {
                    "validation_passed": validation_passed,
                    "unsafe_detected": self._has_unsafe_output(recommendation),
                },
            ),
        }

    def _generate_explanation(self, state: NutritionAgentState) -> dict[str, Any]:
        answer = self.explanation_builder.build(
            status=state.get("status") or "unknown",
            recommendation=state.get("recommendation"),
            clarification=state.get("clarification"),
            error=state.get("error"),
        )
        return {
            "answer": answer,
            "orchestration_trace": self._trace(state, "generate_explanation", "completed"),
        }

    def _finalize_response(self, state: NutritionAgentState) -> dict[str, Any]:
        answer = state.get("answer") or self.explanation_builder.build(
            status=state.get("status") or "unknown",
            recommendation=state.get("recommendation"),
            clarification=state.get("clarification"),
            error=state.get("error"),
        )
        return {
            "answer": answer,
            "orchestration_trace": self._trace(state, "finalize_response", "completed"),
        }

    def _trace(
        self,
        state: NutritionAgentState,
        step: str,
        status: str,
        meta: dict[str, Any] | None = None,
    ) -> list[NutritionAgentTraceStep]:
        trace = list(state.get("orchestration_trace") or [])
        entry: NutritionAgentTraceStep = {"step": step, "status": status}
        if meta:
            entry["meta"] = meta
        trace.append(entry)
        return trace

    def _has_unsafe_output(self, recommendation: dict[str, Any]) -> bool:
        validation = recommendation.get("validation") or {}
        if int(validation.get("unsafe_raw_output_count") or 0) > 0:
            return True
        if int(validation.get("unsafe_label_count") or 0) > 0:
            return True
        for meal in recommendation.get("resolved_meals") or []:
            for item in meal.get("items") or []:
                if item.get("final_output_allowed") is False:
                    return True
                if item.get("consumption_state") == "requires_preparation":
                    return True
        return False


def build_nutrition_agent_graph(
    *,
    core_tool: NutritionCoreRecommendationTool | None = None,
    explanation_builder: NutritionAgentExplanationBuilder | None = None,
    intent_parser: Any | None = None,
    safety_clarification_policy: NutritionAgentSafetyClarificationPolicy | None = None,
) -> NutritionAgentGraph:
    return NutritionAgentGraph(
        core_tool=core_tool,
        explanation_builder=explanation_builder,
        intent_parser=intent_parser,
        safety_clarification_policy=safety_clarification_policy,
    )
