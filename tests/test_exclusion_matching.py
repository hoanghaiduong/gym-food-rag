import unittest

from app.services.nutrition.knowledge.exclusion_matching import (
    normalized_text_matches_exclusion,
    payload_matches_exclusion,
)
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
            "allergen_tags": ["fish"],
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

    def test_seafood_exclusion_matches_fish_and_shellfish_tags(self) -> None:
        self.assertTrue(payload_matches_exclusion({"name": "Tom bien, nuong", "allergen_tags": ["shellfish"]}, "hai san"))
        self.assertTrue(payload_matches_exclusion({"name": "Ca nuc, nuong", "allergen_tags": ["fish"]}, "hai san"))

    def test_fish_exclusion_uses_tags_to_avoid_ca_false_positive(self) -> None:
        self.assertTrue(payload_matches_exclusion({"name": "Ca nuc, nuong", "allergen_tags": ["fish"]}, "ca"))
        self.assertFalse(payload_matches_exclusion({"name": "Ca bat, luoc", "diet_tags": ["produce"]}, "ca"))

    def test_shellfish_exclusion_matches_specific_shellfish_names(self) -> None:
        self.assertTrue(payload_matches_exclusion({"name": "Oc mong tay, nuong"}, "hai san"))
        self.assertTrue(payload_matches_exclusion({"name": "Muc tuoi, hap"}, "hai san"))
        self.assertFalse(payload_matches_exclusion({"name": "Dau co ve, luoc", "diet_tags": ["produce"]}, "hai san"))


if __name__ == "__main__":
    unittest.main()
