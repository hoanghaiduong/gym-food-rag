import json
import tempfile
import unittest
from pathlib import Path

from scripts.lib.nutrition_bench.comparison.metrics import aggregate_case_results
from scripts.lib.nutrition_bench.comparison.runner import BaselineComparisonRunner


def validation_payload(*, passed: bool, calorie: float, macro: float, violation: float = 0.0):
    return {
        "passed": passed,
        "totals": {"energy_kcal": 2000, "protein_g": 120, "carbs_g": 220, "fat_g": 60},
        "calorie_error_pct": calorie,
        "macro_deviation_pct": macro,
        "violation_rate": violation,
        "unsafe_raw_output_count": 0,
        "unsafe_label_count": 0,
        "issues": [],
    }


class FakeWorkflow:
    def __init__(self):
        self.main_flow_calls = 0
        self.pure_generation_calls = 0
        self.rule_based_calls = 0

    def build_profile(self, current_user):
        return {"user_id": current_user["id"], **current_user}

    def _compute_targets(self, profile, request):
        return {"daily_calories": 2000, "protein_g": 120, "carbs_g": 220, "fat_g": 60}

    def _retrieve_candidates(self, profile, request, targets):
        return [{"entity_id": "food_1", "name": "Com ga"}]

    def run_main_flow(self, current_user, request):
        self.main_flow_calls += 1
        return {"validation": validation_payload(passed=True, calorie=2.0, macro=4.0), "response_time_seconds": 1.0}

    def run_pure_generation_baseline(self, profile, request, targets):
        self.pure_generation_calls += 1
        return {"validation": validation_payload(passed=False, calorie=30.0, macro=25.0, violation=0.2), "response_time_seconds": 2.0}

    def run_rule_based_baseline(self, profile, request, targets, candidates):
        self.rule_based_calls += 1
        return {"validation": validation_payload(passed=True, calorie=5.0, macro=8.0), "response_time_seconds": 0.5}


class BrokenPureGenerationWorkflow(FakeWorkflow):
    def run_pure_generation_baseline(self, profile, request, targets):
        raise RuntimeError("LLM unavailable")


class NutritionBaselineComparisonTests(unittest.TestCase):
    def test_aggregation_computes_pass_rates_winners_and_deltas(self):
        case_results = [
            {
                "best_variant": "main_flow",
                "variants": [
                    {"name": "main_flow", "passed": True, "variant_error": False, "calorie_error_pct": 2, "macro_deviation_pct": 4, "violation_rate": 0, "response_time_seconds": 1},
                    {"name": "pure_generation", "passed": False, "variant_error": False, "calorie_error_pct": 30, "macro_deviation_pct": 25, "violation_rate": 0.2, "response_time_seconds": 2},
                    {"name": "rule_based", "passed": True, "variant_error": False, "calorie_error_pct": 5, "macro_deviation_pct": 8, "violation_rate": 0, "response_time_seconds": 0.5},
                ],
            },
            {
                "best_variant": "rule_based",
                "variants": [
                    {"name": "main_flow", "passed": True, "variant_error": False, "calorie_error_pct": 3, "macro_deviation_pct": 3, "violation_rate": 0, "response_time_seconds": 1},
                    {"name": "pure_generation", "passed": False, "variant_error": True},
                    {"name": "rule_based", "passed": True, "variant_error": False, "calorie_error_pct": 1, "macro_deviation_pct": 2, "violation_rate": 0, "response_time_seconds": 0.5},
                ],
            },
        ]

        aggregate = aggregate_case_results(case_results)

        self.assertEqual(aggregate["case_count"], 2)
        self.assertEqual(aggregate["variants"]["main_flow"]["pass_rate"], 1.0)
        self.assertEqual(aggregate["variants"]["pure_generation"]["variant_error_count"], 1)
        self.assertEqual(aggregate["winner_counts"], {"main_flow": 1, "pure_generation": 0, "rule_based": 1})
        self.assertEqual(
            aggregate["variants"]["rule_based"]["delta_vs_main_flow"]["calorie_error_pct"],
            0.5,
        )

    def test_runner_writes_only_summary_by_default(self):
        case = {
            "name": "comparison_case",
            "profile": {"age": 28, "gender": "male", "weight": 72, "height": 172, "activity_level": "moderate", "target_goal": "gain_muscle"},
            "request": {"instruction": "Tao thuc don tang co", "meal_count": 3},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "comparison" / "latest"
            summary = BaselineComparisonRunner(output_dir=output_dir, workflow=FakeWorkflow()).run([case])

            self.assertEqual(summary["case_count"], 1)
            self.assertTrue((output_dir / "comparison_summary.json").exists())
            self.assertFalse((output_dir / "comparison_report.md").exists())
            self.assertFalse((output_dir / "cases").exists())

    def test_runner_records_baseline_errors_without_failing_main_flow(self):
        case = {
            "name": "comparison_case",
            "profile": {"age": 28, "gender": "male", "weight": 72, "height": 172, "activity_level": "moderate", "target_goal": "gain_muscle"},
            "request": {"instruction": "Tao thuc don tang co", "meal_count": 3},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "comparison" / "latest"
            summary = BaselineComparisonRunner(output_dir=output_dir, workflow=BrokenPureGenerationWorkflow()).run(
                [case],
                emit_markdown=True,
                emit_case_files=True,
            )
            payload = json.loads((output_dir / "comparison_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(summary["aggregate"]["variants"]["pure_generation"]["variant_error_count"], 1)
            self.assertTrue((output_dir / "comparison_report.md").exists())
            self.assertTrue((output_dir / "cases" / "comparison_case.json").exists())
            self.assertEqual(payload["artifact_contract"]["canonical_root_touched"], False)

    def test_runner_resume_reuses_completed_cases_from_summary(self):
        first_case = {
            "name": "comparison_case_1",
            "profile": {"age": 28, "gender": "male", "weight": 72, "height": 172, "activity_level": "moderate", "target_goal": "gain_muscle"},
            "request": {"instruction": "Tao thuc don tang co", "meal_count": 3},
        }
        second_case = {
            "name": "comparison_case_2",
            "profile": {"age": 30, "gender": "female", "weight": 60, "height": 165, "activity_level": "active", "target_goal": "maintain"},
            "request": {"instruction": "Tao thuc don duy tri", "meal_count": 3},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "comparison" / "latest"
            first_workflow = FakeWorkflow()
            BaselineComparisonRunner(output_dir=output_dir, workflow=first_workflow).run([first_case])
            self.assertEqual(first_workflow.main_flow_calls, 1)

            resumed_workflow = FakeWorkflow()
            summary = BaselineComparisonRunner(output_dir=output_dir, workflow=resumed_workflow).run(
                [first_case, second_case],
                resume=True,
            )

            self.assertEqual(summary["case_count"], 2)
            self.assertEqual(resumed_workflow.main_flow_calls, 1)
            self.assertEqual([case["case"] for case in summary["case_results"]], ["comparison_case_1", "comparison_case_2"])

    def test_runner_can_run_only_pure_generation_variant(self):
        case = {
            "name": "comparison_case",
            "profile": {"age": 28, "gender": "male", "weight": 72, "height": 172, "activity_level": "moderate", "target_goal": "gain_muscle"},
            "request": {"instruction": "Tao thuc don tang co", "meal_count": 3},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "comparison" / "pure_only"
            workflow = FakeWorkflow()
            summary = BaselineComparisonRunner(output_dir=output_dir, workflow=workflow).run(
                [case],
                selected_variants=("pure_generation",),
            )

            self.assertEqual(workflow.main_flow_calls, 0)
            self.assertEqual(workflow.rule_based_calls, 0)
            self.assertEqual(workflow.pure_generation_calls, 1)
            self.assertEqual(set(summary["aggregate"]["variants"].keys()), {"pure_generation"})

    def test_aggregation_does_not_treat_unselected_variants_as_errors(self):
        case_results = [
            {
                "best_variant": "main_flow",
                "variants": [
                    {"name": "main_flow", "passed": True, "variant_error": False, "calorie_error_pct": 2, "macro_deviation_pct": 4, "violation_rate": 0, "response_time_seconds": 1},
                    {"name": "pure_generation", "passed": False, "variant_error": True},
                ],
            },
            {
                "best_variant": None,
                "variants": [
                    {"name": "pure_generation", "passed": False, "variant_error": True},
                ],
            },
        ]

        aggregate = aggregate_case_results(case_results)

        self.assertEqual(aggregate["variants"]["main_flow"]["attempted_count"], 1)
        self.assertEqual(aggregate["variants"]["main_flow"]["missing_count"], 1)
        self.assertEqual(aggregate["variants"]["main_flow"]["variant_error_count"], 0)
        self.assertEqual(aggregate["variants"]["pure_generation"]["attempted_count"], 2)
        self.assertEqual(aggregate["variants"]["pure_generation"]["variant_error_count"], 2)

    def test_runner_reruns_only_selected_variant_errors_when_resuming(self):
        case = {
            "name": "comparison_case",
            "profile": {"age": 28, "gender": "male", "weight": 72, "height": 172, "activity_level": "moderate", "target_goal": "gain_muscle"},
            "request": {"instruction": "Tao thuc don tang co", "meal_count": 3},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "comparison" / "latest"
            BaselineComparisonRunner(output_dir=output_dir, workflow=BrokenPureGenerationWorkflow()).run([case])

            workflow = FakeWorkflow()
            summary = BaselineComparisonRunner(output_dir=output_dir, workflow=workflow).run(
                [case],
                resume=True,
                selected_variants=("pure_generation",),
                rerun_variant_errors=True,
            )

            variants = {
                variant["name"]: variant
                for variant in summary["case_results"][0]["variants"]
            }
            self.assertEqual(workflow.main_flow_calls, 0)
            self.assertEqual(workflow.rule_based_calls, 0)
            self.assertEqual(workflow.pure_generation_calls, 1)
            self.assertFalse(variants["pure_generation"]["variant_error"])
            self.assertIn("main_flow", variants)
            self.assertIn("rule_based", variants)


if __name__ == "__main__":
    unittest.main()
