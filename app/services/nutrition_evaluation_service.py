import json
from datetime import datetime, timezone

from app.core.paths import LOGS_DIR
from app.schemas.nutrition import NutritionRecommendationRequest
from app.services.nutrition_workflow_service import nutrition_workflow_service


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NutritionEvaluationService:
    def __init__(self):
        self.workflow = nutrition_workflow_service
        self.log_path = LOGS_DIR / "nutrition_evaluations.jsonl"

    def evaluate(
        self,
        current_user: dict,
        request: NutritionRecommendationRequest,
    ) -> dict:
        profile = self.workflow.build_profile(current_user)
        baseline_request = request.model_copy(update={"use_cache": False, "include_debug": False})
        targets = self.workflow._compute_targets(profile, baseline_request)
        candidates = self.workflow._retrieve_candidates(profile, baseline_request, targets)

        main_result = self.workflow.run_main_flow(current_user, baseline_request)
        pure_result = self.workflow.run_pure_generation_baseline(profile, baseline_request, targets)
        rule_result = self.workflow.run_rule_based_baseline(profile, baseline_request, targets, candidates)

        variants = [
            self._variant_summary(
                name="main_flow",
                response_time_seconds=main_result["response_time_seconds"],
                validation=main_result["validation"],
                notes=[
                    "retrieve -> deterministic optimize -> validate -> explain",
                    f"revisions_used={main_result['revisions_used']}",
                ],
            ),
            self._variant_summary(
                name="pure_generation",
                response_time_seconds=pure_result["response_time_seconds"],
                validation=pure_result["validation"],
                notes=["LLM only, no retrieval, no revise loop"],
            ),
            self._variant_summary(
                name="rule_based",
                response_time_seconds=rule_result["response_time_seconds"],
                validation=rule_result["validation"],
                notes=["TDEE + macro targets + static meal selection from retrieved foods"],
            ),
        ]

        best_variant = min(
            variants,
            key=lambda item: (
                0 if item["passed"] else 1,
                item["violation_rate"],
                item["calorie_error_pct"],
                item["macro_deviation_pct"],
            ),
        )["name"]

        response_payload = {
            "request_id": main_result["request_id"],
            "created_at": utc_now_iso(),
            "profile": profile,
            "targets": {
                **targets,
                "calorie_tolerance_pct": baseline_request.calorie_tolerance_pct,
                "macro_tolerance_pct": baseline_request.macro_tolerance_pct,
            },
            "variants": variants,
            "best_variant": best_variant,
            "log_path": str(self.log_path),
        }
        self._append_log(response_payload)
        return response_payload

    def _variant_summary(
        self,
        *,
        name: str,
        response_time_seconds: float,
        validation: dict,
        notes: list[str],
    ) -> dict:
        return {
            "name": name,
            "response_time_seconds": round(response_time_seconds, 3),
            "totals": validation["totals"],
            "calorie_error_kcal": validation["calorie_error_kcal"],
            "calorie_error_pct": validation["calorie_error_pct"],
            "macro_deviation_pct": validation["macro_deviation_pct"],
            "violation_rate": validation["violation_rate"],
            "passed": validation["passed"],
            "notes": notes,
        }

    def _append_log(self, payload: dict) -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


nutrition_evaluation_service = NutritionEvaluationService()
