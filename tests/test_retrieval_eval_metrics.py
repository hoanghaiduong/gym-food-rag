import unittest

from scripts.lib.nutrition_bench.retrieval_eval import metrics, reports


class RetrievalEvalMetricsTests(unittest.TestCase):
    def test_family_retrieval_metrics_uses_explicit_equivalence_groups(self) -> None:
        retrieved_items = [
            {
                "entity_id": "fruit_hit",
                "name": "Xoai chin, tuoi",
                "meal_family_key": "xoai chin",
                "group_name": "Qua chin",
                "meal_role_tags": ["produce_support"],
            },
            {
                "entity_id": "greens_hit",
                "name": "Cai xanh, luoc",
                "meal_family_key": "cai xanh",
                "group_name": "Rau, qua, cu dung lam rau",
                "meal_role_tags": ["produce_support"],
            },
        ]
        positive_items = [
            {
                "entity_id": "fruit_expected",
                "name": "Tao tay, tuoi",
                "meal_family_key": "tao tay",
                "group_name": "Qua chin",
                "meal_role_tags": ["produce_support"],
            },
            {
                "entity_id": "greens_expected",
                "name": "Dau co ve, luoc",
                "meal_family_key": "dau co ve",
                "group_name": "Rau, qua, cu dung lam rau",
                "meal_role_tags": ["produce_support"],
            },
        ]
        expected_groups = [
            {"canonical_entity_id": "fruit_expected", "family_keys": ["fruit_family"]},
            {"canonical_entity_id": "greens_expected", "family_keys": ["greens_family"]},
        ]

        result = metrics.family_retrieval_metrics(
            retrieved_items,
            positive_items,
            2,
            expected_positive_equivalence_groups=expected_groups,
        )

        self.assertEqual(result["expected_family_keys"], ["fruit_family", "greens_family"])
        self.assertEqual(result["hit_family_keys"], ["fruit_family", "greens_family"])
        self.assertEqual(result["recall"], 1.0)

    def test_post_workout_friendly_tag_is_contextual_for_classification(self) -> None:
        def result_row(case_id: str, expected_tags: list[str], observed_tags: list[str]) -> dict:
            return {
                "id": case_id,
                "split": "recommendation",
                "metrics": {
                    "tp": 1,
                    "fp": 0,
                    "fn": 0,
                    "tn": 1,
                    "precision": 1.0,
                    "recall": 1.0,
                    "f1": 1.0,
                    "accuracy": 1.0,
                    "support": 1,
                },
                "tag_sets": {
                    "expected_positive_tags": expected_tags,
                    "observed_positive_tags": observed_tags,
                },
            }

        classification_report, _ = reports.build_retrieval_artifacts(
            [
                result_row("non_post", ["protein_anchor"], ["protein_anchor", "post_workout_friendly"]),
                result_row(
                    "post",
                    ["protein_anchor", "post_workout_friendly"],
                    ["protein_anchor", "post_workout_friendly"],
                ),
            ]
        )

        per_label = classification_report["tasks"]["positive_tag_coverage"]["per_label"]
        self.assertEqual(per_label["post_workout_friendly"]["fp"], 0)
        self.assertEqual(per_label["post_workout_friendly"]["f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
