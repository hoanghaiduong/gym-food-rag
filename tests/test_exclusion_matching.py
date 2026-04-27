import unittest

from app.services.nutrition.knowledge.exclusion_matching import normalized_text_matches_exclusion
from app.services.nutrition.workflow.candidate_features import WorkflowCandidateFeaturesMixin


class _DummyCandidateFeaturesWorkflow(WorkflowCandidateFeaturesMixin):
    def _expand_hint_variants(self, hint: str) -> list[str]:
        return [hint]


class ExclusionMatchingTests(unittest.TestCase):
    def test_peanut_exclusion_does_not_match_ca_lac(self) -> None:
        self.assertFalse(normalized_text_matches_exclusion("ca lac luoc", "lac"))

    def test_peanut_exclusion_matches_real_peanut_items(self) -> None:
        self.assertTrue(normalized_text_matches_exclusion("lac rang", "lac"))
        self.assertTrue(normalized_text_matches_exclusion("xoi lac", "lac"))
        self.assertTrue(normalized_text_matches_exclusion("bo dau phong", "lac"))

    def test_strict_candidate_hint_uses_same_exclusion_logic(self) -> None:
        workflow = _DummyCandidateFeaturesWorkflow()
        fish_candidate = {
            "name": "Ca lac, luoc",
            "meal_family_key": "ca lac",
            "meal_role_tags": ["protein_anchor"],
        }
        peanut_candidate = {
            "name": "Lac rang",
            "meal_family_key": "lac",
            "meal_role_tags": ["fat_support"],
        }

        self.assertFalse(workflow._candidate_matches_strict_hint(fish_candidate, "lac"))
        self.assertTrue(workflow._candidate_matches_strict_hint(peanut_candidate, "lac"))


if __name__ == "__main__":
    unittest.main()
