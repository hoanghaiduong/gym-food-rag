from __future__ import annotations

import time
import uuid
from copy import deepcopy
from typing import Any

from app.schemas.nutrition import NutritionRecommendationRequest

from .models import GenerationAttempt, WorkflowTargets


class WorkflowRuntimeMixin:
    def run_main_flow(
        self,
        current_user: dict[str, Any],
        request: NutritionRecommendationRequest,
    ) -> dict[str, Any]:
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())
        source_profile = self.build_profile(current_user)
        workflow_state = {"request_id": request_id, "status": "running", "trace": []}

        self._record_step(workflow_state, "collect_profile", {"user_id": source_profile["user_id"]})

        cache_payload = self._build_cache_payload(source_profile, request)
        if request.use_cache:
            cached = self.state_store.get_cached_response(cache_payload)
            if cached:
                cached_response = deepcopy(cached)
                cached_response["request_id"] = request_id
                cached_response["cached"] = True
                cached_response["response_time_seconds"] = round(time.perf_counter() - start_time, 3)
                cached_response["workflow_trace"] = [
                    self._trace_entry("redis_exact_cache", "completed", {"hit": True})
                ]
                workflow_state["status"] = "completed"
                workflow_state["response_excerpt"] = {
                    "cached": True,
                    "summary": cached_response["plan"]["summary"],
                }
                self.state_store.save_workflow_state(request_id, workflow_state)
                return cached_response

        parsed_intent = self.intent_parser.parse_intent(source_profile, request)
        effective_profile = self.intent_parser.apply_to_profile(source_profile, parsed_intent)
        effective_request = self.intent_parser.apply_to_request(request, parsed_intent)
        self._record_step(
            workflow_state,
            "parse_intent",
            {
                "source": parsed_intent.source,
                "goal_raw_semantic": parsed_intent.goal_raw_semantic,
                "goal_normalized_internal": parsed_intent.goal_normalized_internal or parsed_intent.goal,
                "planning_strategy": parsed_intent.planning_strategy,
                "confidence": parsed_intent.confidence,
                "meal_count": effective_request.meal_count,
            },
        )

        targets: WorkflowTargets = self._compute_targets(effective_profile, effective_request)
        self._record_step(workflow_state, "compute_targets", {"daily_calories": targets["daily_calories"]})

        candidates = self._retrieve_candidates(effective_profile, effective_request, targets, parsed_intent)
        self._record_step(workflow_state, "retrieve_context", {"candidate_count": len(candidates)})

        generation_result: GenerationAttempt = self._run_deterministic_flow(
            profile=effective_profile,
            request=effective_request,
            targets=targets,
            candidates=candidates,
            intent=parsed_intent,
        )
        self._record_step(
            workflow_state,
            "plan_validate_explain",
            {
                "strategy": generation_result.get("strategy"),
                "passed": generation_result["validation"]["passed"],
            },
        )

        response_payload = self._compose_response(
            request_id=request_id,
            cached=False,
            profile=effective_profile,
            source_profile=source_profile,
            request=effective_request,
            source_request=request,
            targets=targets,
            candidates=candidates,
            generation_result=generation_result,
            parsed_intent=parsed_intent,
            response_time_seconds=round(time.perf_counter() - start_time, 3),
        )

        workflow_state["status"] = "completed"
        workflow_state["trace"] = response_payload["workflow_trace"]
        workflow_state["response_excerpt"] = {
            "cached": False,
            "summary": response_payload["plan"]["summary"],
            "passed": response_payload["validation"]["passed"],
        }
        self.state_store.save_workflow_state(request_id, workflow_state)

        if request.use_cache and response_payload["validation"]["passed"]:
            self.state_store.set_cached_response(cache_payload, response_payload)

        return response_payload

    def run_pure_generation_baseline(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: WorkflowTargets,
    ) -> dict[str, Any]:
        start_time = time.perf_counter()
        raw_text = self.llm.generate_text(
            self._build_pure_generation_prompt(profile, targets, request),
            temperature=0.35,
        )
        plan_json = self._safe_parse_plan(raw_text)
        resolved_plan = self._resolve_plan(plan_json, [], allow_global_lookup=True)
        validation = self._validate_plan(resolved_plan, profile, request, targets, None)
        return {
            "raw_text": raw_text,
            "plan": self._strip_to_structured_plan(resolved_plan),
            "resolved_plan": resolved_plan,
            "validation": validation,
            "grounded_foods": self._grounded_foods_from_resolved_plan(resolved_plan),
            "response_time_seconds": round(time.perf_counter() - start_time, 3),
        }

    def run_rule_based_baseline(
        self,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: WorkflowTargets,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        start_time = time.perf_counter()
        result = self._build_rule_based_attempt(profile, request, targets, candidates, None)
        return {
            "plan": self._strip_to_structured_plan(result["resolved_plan"]),
            "resolved_plan": result["resolved_plan"],
            "validation": result["validation"],
            "grounded_foods": result["grounded_foods"],
            "response_time_seconds": round(time.perf_counter() - start_time, 3),
        }
