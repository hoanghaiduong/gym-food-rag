import unittest

from scripts.lib.nutrition_bench.retrieval_eval import metrics


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


if __name__ == "__main__":
    unittest.main()
