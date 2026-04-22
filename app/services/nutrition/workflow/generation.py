from __future__ import annotations

from typing import Any, Optional

from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.nutrition_intent import NutritionIntent

from .models import GenerationAttempt, WorkflowTargets
from .strings_vi import LLM_GENERATION_FAILED_SUMMARY


class WorkflowGenerationMixin:
    def _run_deterministic_flow(
        self,
        *,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: WorkflowTargets,
        candidates: list[dict[str, Any]],
        intent: Optional[NutritionIntent] = None,
    ) -> GenerationAttempt:
        planning_result = self._build_rule_based_attempt(profile, request, targets, candidates, intent)
        explained_plan = self._attach_plan_explanations(
            profile=profile,
            request=request,
            targets=targets,
            resolved_plan=planning_result["resolved_plan"],
            validation=planning_result["validation"],
            intent=intent,
        )
        planning_result["resolved_plan"] = explained_plan
        planning_result["plan_json"] = self._strip_to_structured_plan(explained_plan)
        planning_result["grounded_foods"] = self._grounded_foods_from_resolved_plan(explained_plan)
        planning_result["attempt_count"] = 0
        planning_result["strategy"] = "deterministic_optimizer"
        planning_result["explanation_mode"] = (
            "llm_explainer" if explained_plan.get("reasoning") else "deterministic_explainer"
        )
        planning_result["candidate_diagnostics"] = self._candidate_diagnostics(
            candidates,
            request,
            targets,
            profile,
            intent,
        )
        return planning_result

    def _run_revision_loop(
        self,
        *,
        profile: dict[str, Any],
        request: NutritionRecommendationRequest,
        targets: WorkflowTargets,
        candidates: list[dict[str, Any]],
        intent: Optional[NutritionIntent] = None,
    ) -> GenerationAttempt:
        attempts: list[GenerationAttempt] = []
        previous_raw = ""
        previous_plan = None
        validation = None

        for attempt in range(request.max_revision_rounds + 1):
            prompt = (
                self._build_main_prompt(profile, request, targets, candidates)
                if attempt == 0
                else self._build_revision_prompt(
                    profile=profile,
                    request=request,
                    targets=targets,
                    candidates=candidates,
                    previous_plan=previous_plan,
                    previous_raw=previous_raw,
                    validation=validation,
                    attempt=attempt,
                )
            )

            try:
                raw_text = self.llm.generate_text(prompt, temperature=0.15 if attempt else 0.25)
            except Exception as exc:
                failed_plan = {
                    "summary": LLM_GENERATION_FAILED_SUMMARY,
                    "reasoning": [str(exc)],
                    "meals": [],
                }
                failed_resolved_plan = self._resolve_plan(failed_plan, candidates, allow_global_lookup=False)
                failed_validation = self._validate_plan(
                    failed_resolved_plan,
                    profile,
                    request,
                    targets,
                    intent,
                    attempt=attempt,
                )
                attempts.append(
                    {
                        "attempt": attempt,
                        "strategy": "llm_error",
                        "raw_text": "",
                        "plan_json": failed_plan,
                        "resolved_plan": failed_resolved_plan,
                        "validation": failed_validation,
                    }
                )
                previous_raw = str(exc)
                previous_plan = failed_plan
                validation = failed_validation
                break

            plan_json = self._safe_parse_plan(raw_text)
            resolved_plan = self._resolve_plan(plan_json, candidates, allow_global_lookup=False)
            validation = self._validate_plan(
                resolved_plan,
                profile,
                request,
                targets,
                intent,
                attempt=attempt,
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "strategy": "llm_generate" if attempt == 0 else "llm_revise",
                    "raw_text": raw_text,
                    "plan_json": plan_json,
                    "resolved_plan": resolved_plan,
                    "validation": validation,
                }
            )
            if validation["passed"]:
                break
            previous_raw = raw_text
            previous_plan = plan_json

        llm_attempt_count = len(attempts)
        fallback_attempt = self._build_rule_based_attempt(profile, request, targets, candidates, intent)
        attempts.append(fallback_attempt)

        best = self._pick_best_attempt(attempts)
        best["attempt_count"] = llm_attempt_count
        best["grounded_foods"] = self._grounded_foods_from_resolved_plan(best["resolved_plan"])
        best["candidate_diagnostics"] = self._candidate_diagnostics(candidates, request, targets, profile, intent)
        return best

    def _attempt_sort_key(self, item: GenerationAttempt):
        validation = item["validation"]
        return (
            0 if validation["passed"] else 1,
            validation["violation_rate"],
            validation["calorie_error_pct"],
            validation["macro_deviation_pct"],
            0 if item.get("strategy") == "rule_based_fallback" else 1,
        )
