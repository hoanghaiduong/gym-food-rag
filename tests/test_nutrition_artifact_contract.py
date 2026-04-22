from __future__ import annotations

from types import SimpleNamespace
import json
import tempfile
import unittest
from pathlib import Path

from scripts.judge_production_readiness import evaluate_recommendation_gate
from scripts.lib.nutrition_bench.common.artifacts import (
    ARTIFACT_ROOT,
    ROOT_ALLOWED_ENTRY_NAMES,
    ROOT_CANONICAL_FILENAMES,
    copy_debug_run_to_canonical,
    find_latest_debug_run,
    prune_debug_pipeline_runs,
    referenced_debug_roots,
)
from scripts.lib.nutrition_bench.retrieval_eval import io as retrieval_io


class NutritionArtifactContractTests(unittest.TestCase):
    def build_retrieval_args(self, **overrides: object) -> SimpleNamespace:
        payload = {
            "output": None,
            "classification_report_output": None,
            "confusion_matrix_output": None,
            "checkpoint_output": None,
            "artifact_mode": "canonical",
            "emit_confusion_matrix": False,
            "limit": None,
            "split": None,
            "case_ids": None,
            "run_name": "ignored_in_canonical_mode",
            "promote_to_canonical": False,
            "resume": False,
        }
        payload.update(overrides)
        return SimpleNamespace(**payload)

    def test_root_whitelist_matches_canonical_contract(self) -> None:
        self.assertEqual(
            ROOT_CANONICAL_FILENAMES,
            {
                "intent_dataset_evaluation.json",
                "intent_classification_report.json",
                "retrieval_dataset_lint.json",
                "retrieval_dataset_evaluation.json",
                "retrieval_classification_report.json",
                "summary.json",
                "production_scorecard.json",
            },
        )
        self.assertEqual(ROOT_ALLOWED_ENTRY_NAMES, ROOT_CANONICAL_FILENAMES | {"_debug"})

    def test_filtered_retrieval_run_routes_to_debug_without_auxiliary_noise(self) -> None:
        args = self.build_retrieval_args(split="stress", limit=10)
        layout, output_path, classification_path, confusion_path, checkpoint_path = (
            retrieval_io.resolve_output_targets(args)
        )

        self.assertFalse(layout.writes_to_canonical)
        self.assertTrue(str(output_path).startswith(str(ARTIFACT_ROOT / "_debug")))
        self.assertEqual(output_path.name, retrieval_io.DEFAULT_OUTPUT.name)
        self.assertEqual(classification_path.name, retrieval_io.DEFAULT_CLASSIFICATION_OUTPUT.name)
        self.assertIsNone(confusion_path)
        self.assertIsNone(checkpoint_path)

    def test_promoted_retrieval_run_can_write_back_to_canonical(self) -> None:
        args = self.build_retrieval_args(split="stress", limit=10, promote_to_canonical=True)
        layout, output_path, classification_path, confusion_path, checkpoint_path = (
            retrieval_io.resolve_output_targets(args)
        )

        self.assertTrue(layout.writes_to_canonical)
        self.assertEqual(output_path, retrieval_io.DEFAULT_OUTPUT)
        self.assertEqual(classification_path, retrieval_io.DEFAULT_CLASSIFICATION_OUTPUT)
        self.assertIsNone(confusion_path)
        self.assertIsNone(checkpoint_path)

    def test_production_judge_uses_summary_metrics_without_case_files(self) -> None:
        results = [
            {
                "case": f"case_{index}",
                "metrics": {
                    "calorie_error_pct": 2.0,
                    "macro_deviation_pct": 3.0,
                    "response_time_seconds": 12.0,
                },
            }
            for index in range(50)
        ]
        summary_payload = {
            "passed_cases": 50,
            "total_cases": 50,
            "summary_metrics": {
                "validation_pass_rate": 1.0,
                "meal_realism_pass_rate": 1.0,
                "main_meal_anchor_pass_rate": 1.0,
                "discouraged_item_rate": 0.0,
                "allergy_issue_count": 0,
                "diet_issue_count": 0,
                "unsafe_raw_output_count": 0,
                "unsafe_label_count": 0,
                "substituted_to_safe_variant_count": 2,
            },
            "results": results,
        }

        gate = evaluate_recommendation_gate(summary_payload)

        self.assertTrue(gate["passed"])
        self.assertEqual(gate["production_kpi"]["case_count"]["actual"], 50.0)
        self.assertEqual(gate["production_kpi"]["allergy_violation_rate"]["actual"], 0.0)
        self.assertEqual(gate["production_kpi"]["diet_violation_rate"]["actual"], 0.0)
        self.assertEqual(gate["production_kpi"]["unsafe_raw_output_count"]["actual"], 0)

    def test_find_latest_debug_run_uses_required_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "_debug" / "retrieval"
            older = root / "older_run"
            newer_incomplete = root / "newer_incomplete"
            latest_complete = root / "latest_complete"
            for directory in (older, newer_incomplete, latest_complete):
                directory.mkdir(parents=True, exist_ok=True)

            for name in (
                "retrieval_dataset_evaluation.json",
                "retrieval_classification_report.json",
                "retrieval_dataset_lint.json",
            ):
                (older / name).write_text("{}", encoding="utf-8")
                (latest_complete / name).write_text("{}", encoding="utf-8")
            (newer_incomplete / "retrieval_dataset_evaluation.json").write_text("{}", encoding="utf-8")

            latest = find_latest_debug_run(
                "retrieval",
                required_filenames=(
                    "retrieval_dataset_evaluation.json",
                    "retrieval_classification_report.json",
                    "retrieval_dataset_lint.json",
                ),
                debug_root=Path(tmpdir) / "_debug",
            )

            self.assertEqual(latest, latest_complete)

    def test_promote_and_prune_debug_runs_keeps_referenced_dataset_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_root = Path(tmpdir) / "nutrition_case_runs"
            debug_root = artifact_root / "_debug"
            retrieval_root = debug_root / "retrieval"
            suite_dir = retrieval_root / "suite_source"
            latest_run = retrieval_root / "latest_complete"
            stale_run = retrieval_root / "stale_run"
            for directory in (suite_dir, latest_run, stale_run):
                directory.mkdir(parents=True, exist_ok=True)

            suite_file = suite_dir / "retrieval_golden_cases.generated.jsonl"
            suite_file.write_text("{}\n", encoding="utf-8")

            evaluation_payload = {
                "dataset_path": str(suite_file),
                "case_count": 1,
                "average_metrics": {},
            }
            (latest_run / "retrieval_dataset_evaluation.json").write_text(
                json.dumps(evaluation_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            (latest_run / "retrieval_classification_report.json").write_text("{}", encoding="utf-8")
            (latest_run / "retrieval_dataset_lint.json").write_text("{}", encoding="utf-8")
            (stale_run / "retrieval_dataset_evaluation.json").write_text("{}", encoding="utf-8")
            (stale_run / "retrieval_classification_report.json").write_text("{}", encoding="utf-8")
            (stale_run / "retrieval_dataset_lint.json").write_text("{}", encoding="utf-8")

            copied = copy_debug_run_to_canonical(
                latest_run,
                filenames=(
                    "retrieval_dataset_evaluation.json",
                    "retrieval_classification_report.json",
                    "retrieval_dataset_lint.json",
                ),
                artifact_root=artifact_root,
            )
            keep_dirs = [latest_run, *referenced_debug_roots(list(copied.values()))]
            removed = prune_debug_pipeline_runs(
                "retrieval",
                keep_dirs=keep_dirs,
                debug_root=debug_root,
            )

            self.assertTrue((artifact_root / "retrieval_dataset_evaluation.json").exists())
            self.assertTrue((artifact_root / "retrieval_classification_report.json").exists())
            self.assertTrue((artifact_root / "retrieval_dataset_lint.json").exists())
            self.assertEqual({path.name for path in removed}, {"stale_run"})
            self.assertTrue(latest_run.exists())
            self.assertTrue(suite_dir.exists())


if __name__ == "__main__":
    unittest.main()
