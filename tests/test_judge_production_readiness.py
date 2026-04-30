import unittest

from scripts import judge_production_readiness as judge


class JudgeProductionReadinessTests(unittest.TestCase):
    def test_retrieval_top4_diagnostic_uses_equivalence_precision(self) -> None:
        retrieval_report = {
            "case_count": 306,
            "support_per_case": 4,
            "exact_id_precision_at_10_ceiling": 0.4,
            "average_metrics": {
                "equivalence_recall_at_20": 1.0,
                "required_tag_hit_rate": 1.0,
                "allergy_unsafe_hit_count": 0,
                "must_exclude_hit_count": 0,
                "forbidden_output_hit_count": 0,
                "equivalence_precision_at_4": 0.75,
                "equivalence_precision_at_10": 0.7,
                "exact_id_precision_at_4": 0.25,
                "exact_id_precision_at_10": 0.2,
                "exact_id_recall_at_20": 0.5,
                "exact_id_mrr_at_20": 0.5,
                "family_duplication_rate_top10": 0.0,
            },
            "split_average_metrics": {
                "recommendation": {"equivalence_recall_at_20": 1.0},
                "noisy": {"equivalence_recall_at_20": 1.0},
                "stress": {"equivalence_recall_at_20": 1.0},
            },
        }
        retrieval_classification = {"tasks": {"positive_tag_coverage": {"per_label": {}}}}

        result = judge.evaluate_retrieval_gate(retrieval_report, retrieval_classification)
        diagnostic = result["diagnostic_kpi"]

        self.assertTrue(result["passed"])
        self.assertTrue(diagnostic["equivalence_precision_at_4"]["passed"])
        self.assertEqual(diagnostic["precision_at_4"]["basis"], "equivalence_precision_at_4")
        self.assertEqual(diagnostic["exact_id_precision_at_4_observed"]["actual"], 0.25)
        self.assertTrue(diagnostic["exact_id_recall_at_20_observed"]["passed"])


if __name__ == "__main__":
    unittest.main()
