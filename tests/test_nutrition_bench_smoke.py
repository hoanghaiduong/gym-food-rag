from __future__ import annotations

import importlib
import os
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_EVAL_MODULES = [
    "scripts.lib.nutrition_bench.retrieval_eval.io",
    "scripts.lib.nutrition_bench.retrieval_eval.lint",
    "scripts.lib.nutrition_bench.retrieval_eval.metrics",
    "scripts.lib.nutrition_bench.retrieval_eval.reports",
    "scripts.lib.nutrition_bench.retrieval_eval.runner",
]
RETRIEVAL_SUITE_MODULES = [
    "scripts.lib.nutrition_bench.retrieval_suite.assembly",
    "scripts.lib.nutrition_bench.retrieval_suite.generators",
    "scripts.lib.nutrition_bench.retrieval_suite.scoring",
]
INTENT_EVAL_MODULES = [
    "scripts.lib.nutrition_bench.intent_eval",
    "scripts.lib.nutrition_bench.intent_eval.reports",
]
TEST_CASE_MODULES = [
    "scripts.lib.nutrition_bench.common.artifacts",
    "scripts.lib.nutrition_bench.common.auth",
    "scripts.lib.nutrition_bench.common.http",
    "scripts.lib.nutrition_bench.common.reports",
    "scripts.lib.nutrition_bench.test_cases.cases",
    "scripts.lib.nutrition_bench.test_cases.metrics",
    "scripts.lib.nutrition_bench.test_cases.runner",
]
CLI_WRAPPERS = [
    PROJECT_ROOT / "scripts" / "evaluate_retrieval_dataset.py",
    PROJECT_ROOT / "scripts" / "build_retrieval_eval_suite.py",
    PROJECT_ROOT / "scripts" / "lint_retrieval_dataset.py",
    PROJECT_ROOT / "scripts" / "promote_nutrition_case_artifacts.py",
    PROJECT_ROOT / "scripts" / "test_nutrition_cases.py",
]
OPTIONAL_IMPORT_HINTS = ("email_validator", "email-validator", "pydantic_settings")


def is_optional_dependency_error(exc: Exception) -> bool:
    message = str(exc)
    return any(hint in message for hint in OPTIONAL_IMPORT_HINTS)


class NutritionBenchSmokeTests(unittest.TestCase):
    def test_retrieval_eval_modules_import(self) -> None:
        for module_name in RETRIEVAL_EVAL_MODULES:
            with self.subTest(module=module_name):
                try:
                    module = importlib.import_module(module_name)
                except (ImportError, ModuleNotFoundError) as exc:
                    if is_optional_dependency_error(exc):
                        continue
                    raise
                self.assertIsNotNone(module)

    def test_retrieval_suite_modules_import(self) -> None:
        for module_name in RETRIEVAL_SUITE_MODULES:
            with self.subTest(module=module_name):
                try:
                    module = importlib.import_module(module_name)
                except (ImportError, ModuleNotFoundError) as exc:
                    if is_optional_dependency_error(exc):
                        continue
                    raise
                self.assertIsNotNone(module)

    def test_intent_eval_modules_import(self) -> None:
        for module_name in INTENT_EVAL_MODULES:
            with self.subTest(module=module_name):
                try:
                    module = importlib.import_module(module_name)
                except (ImportError, ModuleNotFoundError) as exc:
                    if is_optional_dependency_error(exc):
                        continue
                    raise
                self.assertIsNotNone(module)

    def test_test_case_modules_import(self) -> None:
        for module_name in TEST_CASE_MODULES:
            with self.subTest(module=module_name):
                try:
                    module = importlib.import_module(module_name)
                except (ImportError, ModuleNotFoundError) as exc:
                    if is_optional_dependency_error(exc):
                        continue
                    raise
                self.assertIsNotNone(module)

    def test_retrieval_runner_uses_public_module_contract(self) -> None:
        runner_source = (PROJECT_ROOT / "scripts" / "lib" / "nutrition_bench" / "retrieval_eval" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("from . import io, metrics, reports", runner_source)

    def test_cli_wrappers_help(self) -> None:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"

        for script_path in CLI_WRAPPERS:
            with self.subTest(script=script_path.name):
                completed = subprocess.run(
                    [sys.executable, "-X", "utf8", str(script_path), "--help"],
                    cwd=PROJECT_ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=completed.stderr or completed.stdout,
                )
                self.assertIn("usage:", completed.stdout.lower())


if __name__ == "__main__":
    unittest.main()
