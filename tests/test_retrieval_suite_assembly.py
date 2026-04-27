import unittest

from scripts.lib.nutrition_bench.retrieval_suite.assembly import build_positive_tags
from scripts.lib.nutrition_bench.retrieval_suite.case_payload import build_case_payload


class RetrievalSuiteAssemblyTests(unittest.TestCase):
    def test_build_positive_tags_follow_explicit_produce_hints(self) -> None:
        tags = build_positive_tags(
            raw_goal="eat_healthier",
            style="post_workout",
            allergy_tags=[],
            must_include=["rau xanh", "trai cay"],
        )

        self.assertEqual(tags, ["produce_support"])

    def test_build_positive_tags_preserve_explicit_macro_roles(self) -> None:
        tags = build_positive_tags(
            raw_goal="support_training",
            style="post_workout",
            allergy_tags=[],
            must_include=["gao", "trung"],
        )

        self.assertIn("carb_anchor", tags)
        self.assertIn("protein_anchor", tags)
        self.assertIn("post_workout_friendly", tags)

    def test_case_payload_splits_equivalence_and_exact_anchor_ids(self) -> None:
        positives = [
            {"entity_id": "exact_1", "name": "Com trang", "meal_role_tags": ["carb_anchor"]},
            {"entity_id": "family_1", "name": "Gao lut", "meal_role_tags": ["carb_anchor"]},
        ]
        payload = build_case_payload(
            case_id="case_1",
            split="recommendation",
            query="test",
            profile={},
            request_context={},
            positives=positives,
            negatives=[],
            must_exclude_ids=[],
            expected_positive_tags=[],
            expected_negative_tags=[],
            notes=[],
            equivalence_positive_items=positives,
            exact_anchor_items=positives[:1],
        )

        self.assertEqual(payload["expected_positive_entity_ids"], ["exact_1", "family_1"])
        self.assertEqual(payload["equivalence_positive_entity_ids"], ["exact_1", "family_1"])
        self.assertEqual(payload["exact_anchor_entity_ids"], ["exact_1"])


if __name__ == "__main__":
    unittest.main()
