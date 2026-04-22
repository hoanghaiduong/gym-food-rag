from __future__ import annotations

import unittest

from scripts.lib.nutrition_bench.retrieval_eval import lint as retrieval_lint


class _FakeKnowledgeService:
    def __init__(self, responses: dict[str, dict[str, object] | None], jsonl_path: str) -> None:
        self._responses = responses
        self.jsonl_path = jsonl_path

    def resolve_food_reference(
        self,
        *,
        entity_id=None,
        food_name=None,
        candidate_map=None,
        allow_global_lookup=False,
        allow_blocked_lookup=False,
    ):
        del food_name, candidate_map, allow_global_lookup, allow_blocked_lookup
        return self._responses.get(entity_id)


class RetrievalDatasetLintTests(unittest.TestCase):
    def test_lint_case_flags_unsafe_positive_entities_from_master_lookup(self) -> None:
        case = {
            "id": "retrieval_reco_unsafe_raw",
            "expected_positive_entity_ids": ["food_4072"],
            "expected_negative_entity_ids": [],
            "must_exclude_entity_ids": [],
            "forbidden_output_entity_ids": [],
            "forbidden_output_patterns": [],
            "allowed_direct_edible_exceptions": [],
            "profile": {"dietary_preference": "vegetarian"},
        }
        knowledge_service = _FakeKnowledgeService(
            responses={
                "food_4072": {
                    "entity_id": "food_4072",
                    "name": "Rau giền cơm, tươi",
                    "diet_tags": ["vegetarian", "vegan"],
                    "final_output_allowed": False,
                    "consumption_state": "requires_preparation",
                    "unsafe_output_reason": "raw_starchy_staple",
                }
            },
            jsonl_path="data/processed/nutrition_kb_master.jsonl",
        )

        issues = retrieval_lint.lint_case(case, knowledge_service=knowledge_service)

        issue_codes = {issue["code"] for issue in issues}
        self.assertIn("unsafe_positive_entities", issue_codes)
        unsafe_issue = next(issue for issue in issues if issue["code"] == "unsafe_positive_entities")
        self.assertEqual(
            unsafe_issue["details"]["knowledge_jsonl_path"],
            "data/processed/nutrition_kb_master.jsonl",
        )
        self.assertEqual(unsafe_issue["details"]["items"][0]["entity_id"], "food_4072")

    def test_lint_case_keeps_unresolved_positive_entities_for_missing_ids(self) -> None:
        case = {
            "id": "retrieval_reco_missing_positive",
            "expected_positive_entity_ids": ["food_missing"],
            "expected_negative_entity_ids": [],
            "must_exclude_entity_ids": [],
            "forbidden_output_entity_ids": [],
            "forbidden_output_patterns": [],
            "allowed_direct_edible_exceptions": [],
            "profile": {"dietary_preference": "omnivore"},
        }
        knowledge_service = _FakeKnowledgeService(
            responses={},
            jsonl_path="data/processed/nutrition_kb_master.jsonl",
        )

        issues = retrieval_lint.lint_case(case, knowledge_service=knowledge_service)

        issue_codes = {issue["code"] for issue in issues}
        self.assertIn("unresolved_positive_entities", issue_codes)
        self.assertNotIn("unsafe_positive_entities", issue_codes)
        unresolved_issue = next(issue for issue in issues if issue["code"] == "unresolved_positive_entities")
        self.assertEqual(unresolved_issue["details"]["entity_ids"], ["food_missing"])


if __name__ == "__main__":
    unittest.main()
