import unittest

from app.services.nutrition.workflow.candidate_features import WorkflowCandidateFeaturesMixin


class _DummyWorkflow(WorkflowCandidateFeaturesMixin):
    def _expand_hint_variants(self, hint: str) -> list[str]:
        return [hint]


class RuntimeHintMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _DummyWorkflow()

    def test_generic_fish_hint_matches_real_fish_only(self) -> None:
        fish_candidate = {
            "name": "Ca nuc, nuong",
            "meal_family_key": "ca nuc",
            "meal_role_tags": ["protein_anchor"],
        }
        squid_candidate = {
            "name": "Muc tuoi, hap",
            "meal_family_key": "muc",
            "meal_role_tags": ["protein_anchor"],
        }
        eggplant_candidate = {
            "name": "Ca bat, luoc",
            "meal_family_key": "ca bat",
            "meal_role_tags": ["produce_support"],
        }

        self.assertTrue(self.workflow._candidate_matches_hint(fish_candidate, "ca"))
        self.assertFalse(self.workflow._candidate_matches_hint(squid_candidate, "ca"))
        self.assertFalse(self.workflow._candidate_matches_hint(eggplant_candidate, "ca"))

    def test_egg_hint_does_not_match_bean_named_with_trung(self) -> None:
        bean_candidate = {
            "name": "Dau trung cuoc, hat kho",
            "meal_family_key": "dau trung cuoc",
            "meal_role_tags": ["protein_anchor"],
        }
        egg_candidate = {
            "name": "Trung ga, luoc",
            "meal_family_key": "trung ga",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertFalse(self.workflow._candidate_matches_hint(bean_candidate, "trung"))
        self.assertTrue(self.workflow._candidate_matches_hint(egg_candidate, "trung"))

    def test_rice_hint_does_not_match_ngao_substring(self) -> None:
        clam_candidate = {
            "name": "Ngao hoa hap sa",
            "meal_family_key": "ngao hoa hap sa",
            "meal_role_tags": ["protein_anchor", "carb_anchor"],
        }
        rice_candidate = {
            "name": "Com te mieng bat",
            "meal_family_key": "com te",
            "meal_role_tags": ["carb_anchor"],
        }

        self.assertFalse(self.workflow._candidate_matches_hint(clam_candidate, "gao"))
        self.assertTrue(self.workflow._candidate_matches_hint(rice_candidate, "gao"))

    def test_rice_hint_does_not_match_non_carb_rice_paper_name(self) -> None:
        nem_candidate = {
            "name": "Nem chao",
            "name_en": "Pork skin rolled with rice paper",
            "meal_family_key": "nem",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertFalse(self.workflow._candidate_matches_hint(nem_candidate, "gao"))

    def test_greens_hint_matches_cooked_vegetables_not_root(self) -> None:
        eggplant_candidate = {
            "name": "Ca tim, luoc",
            "meal_family_key": "ca tim",
            "meal_role_tags": ["produce_support"],
        }
        longbean_candidate = {
            "name": "Dau dua, luoc",
            "meal_family_key": "dau dua",
            "meal_role_tags": ["produce_support"],
        }
        carrot_candidate = {
            "name": "Ca rot, luoc",
            "meal_family_key": "ca rot",
            "meal_role_tags": ["produce_support"],
        }

        self.assertTrue(self.workflow._candidate_matches_hint(eggplant_candidate, "rau xanh"))
        self.assertTrue(self.workflow._candidate_matches_hint(longbean_candidate, "rau xanh"))
        self.assertFalse(self.workflow._candidate_matches_hint(carrot_candidate, "rau xanh"))


if __name__ == "__main__":
    unittest.main()
