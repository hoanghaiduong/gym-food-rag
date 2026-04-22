from __future__ import annotations

from typing import Any

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent

from .models import GenerationAttempt, WorkflowTargets


class WorkflowResponseRuntimeMixin:
    def _build_cache_payload(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> dict[str, Any]:
        return {
            "user_id": profile["user_id"],
            "semantic_parser_version": self.intent_parser.version,
            "profile": {key: value for key, value in profile.items() if key != "full_name"},
            "request": request.model_dump(exclude={"use_cache", "include_debug"}),
        }

    def _compose_response(
        self,
        *,
        request_id: str,
        cached: bool,
        profile: dict[str, Any],
        source_profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        source_request: NutritionRecommendationRequest,
        targets: WorkflowTargets,
        candidates: list[dict[str, Any]],
        generation_result: GenerationAttempt,
        parsed_intent: NutritionIntent,
        response_time_seconds: float,
    ) -> dict[str, Any]:
        debug_payload = None
        if request.include_debug:
            debug_payload = {
                "raw_model_output": generation_result["raw_text"],
                "attempt_count": generation_result["attempt_count"],
                "selected_strategy": generation_result.get("strategy"),
                "explanation_mode": generation_result.get("explanation_mode"),
                "candidate_diagnostics": generation_result.get("candidate_diagnostics"),
                "parsed_intent": parsed_intent.model_dump(mode="json"),
                "source_profile": source_profile,
                "effective_profile": profile,
                "source_request": source_request.model_dump(mode="json"),
                "effective_request": request.model_dump(mode="json"),
            }

        return {
            "request_id": request_id,
            "cached": cached,
            "engine": {
                "llm_backend": getattr(self.llm, "backend", "ollama"),
                "llm_model": self.llm.model,
                "planner": "deterministic_optimizer",
                "retrieval": "qdrant_hybrid",
                "cache": "redis_exact_cache",
                "state": "redis_workflow_state",
                "semantic_parser": self.intent_parser.version,
            },
            "profile": profile,
            "targets": {
                **targets,
                "calorie_tolerance_pct": request.calorie_tolerance_pct,
                "macro_tolerance_pct": request.macro_tolerance_pct,
            },
            "plan": self._strip_to_structured_plan(generation_result["resolved_plan"]),
            "resolved_meals": generation_result["resolved_plan"]["meals"],
            "totals": generation_result["validation"]["totals"],
            "validation": generation_result["validation"],
            "retrieved_context": candidates,
            "grounded_foods": generation_result["grounded_foods"],
            "revisions_used": max(generation_result["attempt_count"] - 1, 0),
            "response_time_seconds": response_time_seconds,
            "workflow_trace": [
                self._trace_entry("collect_profile", "completed", {"user_id": profile["user_id"]}),
                self._trace_entry(
                    "parse_intent",
                    "completed",
                    {
                        "source": parsed_intent.source,
                        "goal_raw_semantic": parsed_intent.goal_raw_semantic,
                        "goal_normalized_internal": parsed_intent.goal_normalized_internal or parsed_intent.goal,
                        "planning_strategy": parsed_intent.planning_strategy,
                        "confidence": parsed_intent.confidence,
                    },
                ),
                self._trace_entry("compute_targets", "completed", {"daily_calories": targets["daily_calories"]}),
                self._trace_entry("retrieve_context", "completed", {"candidate_count": len(candidates)}),
                self._trace_entry(
                    "plan_validate_explain",
                    "completed",
                    {
                        "strategy": generation_result.get("strategy"),
                        "explanation_mode": generation_result.get("explanation_mode"),
                        "passed": generation_result["validation"]["passed"],
                    },
                ),
                self._trace_entry("return_result", "completed", {"cached": cached}),
            ],
            "debug": debug_payload,
        }
