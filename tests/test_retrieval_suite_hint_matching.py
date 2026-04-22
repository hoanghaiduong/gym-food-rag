import unittest

from scripts.lib.nutrition_bench.retrieval_suite.hint_matching import (
    candidate_equivalence_family_keys,
    candidate_matches_benchmark_hint,
)


class RetrievalSuiteHintMatchingTests(unittest.TestCase):
    def test_squid_does_not_match_fish_hint(self) -> None:
        candidate = {
            "entity_id": "squid_1",
            "name": "Muc tuoi, hap",
            "name_en": "Cuttle fish squid, steamed",
            "meal_family_key": "muc",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertFalse(candidate_matches_benchmark_hint(candidate, "ca"))

    def test_shellfish_does_not_match_egg_hint(self) -> None:
        candidate = {
            "entity_id": "shellfish_1",
            "name": "So huyet, luoc",
            "name_en": "Blood cockle, boiled",
            "meal_family_key": "so huyet",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertFalse(candidate_matches_benchmark_hint(candidate, "trung"))

    def test_green_banana_does_not_match_greens_hint(self) -> None:
        candidate = {
            "entity_id": "banana_1",
            "name": "Chuoi xanh, tuoi",
            "name_en": "Banana common varieties, unripe",
            "meal_family_key": "chuoi xanh",
            "meal_role_tags": ["carb_anchor", "produce_support"],
        }

        self.assertFalse(candidate_matches_benchmark_hint(candidate, "rau xanh"))

    def test_real_fish_still_matches_fish_hint(self) -> None:
        candidate = {
            "entity_id": "fish_1",
            "name": "Ca nuc, nuong",
            "name_en": "Fish, grilled",
            "meal_family_key": "ca nuc",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertTrue(candidate_matches_benchmark_hint(candidate, "ca"))

    def test_bean_named_with_trung_does_not_match_egg_hint(self) -> None:
        candidate = {
            "entity_id": "bean_1",
            "name": "Dau trung cuoc, hat kho",
            "meal_family_key": "dau trung cuoc",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertFalse(candidate_matches_benchmark_hint(candidate, "trung"))

    def test_dried_seed_like_items_do_not_match_greens_hint(self) -> None:
        candidate = {
            "entity_id": "seed_1",
            "name": "Hat sen, kho",
            "name_en": "Dried lotus seed",
            "meal_family_key": "hat sen",
            "meal_role_tags": ["produce_support"],
        }

        self.assertFalse(candidate_matches_benchmark_hint(candidate, "rau xanh"))

    def test_fruit_hint_matches_real_fruit_from_group_context(self) -> None:
        candidate = {
            "entity_id": "fruit_1",
            "name": "Cam chanh, tuoi",
            "meal_family_key": "cam chanh",
            "group_name": "Qua chin",
            "meal_role_tags": ["produce_support"],
        }

        self.assertTrue(candidate_matches_benchmark_hint(candidate, "trai cay"))

    def test_rice_named_with_cam_does_not_match_fruit_hint(self) -> None:
        candidate = {
            "entity_id": "rice_1",
            "name": "Xoi nep cam",
            "name_en": "Purple sticky rice",
            "meal_family_key": "xoi nep cam",
            "meal_role_tags": ["carb_anchor"],
        }

        self.assertFalse(candidate_matches_benchmark_hint(candidate, "trai cay"))

    def test_equivalence_keys_are_family_strict(self) -> None:
        rice_candidate = {
            "entity_id": "rice_1",
            "name": "Xoi nep cam",
            "name_en": "Rice glutinous cooked",
            "meal_family_key": "xoi nep cam",
            "meal_role_tags": ["carb_anchor"],
        }
        banana_candidate = {
            "entity_id": "banana_1",
            "name": "Chuoi xanh, tuoi",
            "name_en": "Banana common varieties, unripe",
            "meal_family_key": "chuoi xanh",
            "meal_role_tags": ["carb_anchor", "produce_support"],
        }
        squid_candidate = {
            "entity_id": "squid_1",
            "name": "Muc tuoi, hap",
            "name_en": "Cuttle fish squid, steamed",
            "meal_family_key": "muc",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertEqual(candidate_equivalence_family_keys(rice_candidate), ["rice_family"])
        self.assertEqual(candidate_equivalence_family_keys(banana_candidate), ["fruit_family"])
        self.assertEqual(candidate_equivalence_family_keys(squid_candidate), ["id:squid_1"])


if __name__ == "__main__":
    unittest.main()
