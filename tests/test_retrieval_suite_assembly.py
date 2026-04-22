import unittest

from scripts.lib.nutrition_bench.retrieval_suite.assembly import build_positive_tags


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


if __name__ == "__main__":
    unittest.main()
