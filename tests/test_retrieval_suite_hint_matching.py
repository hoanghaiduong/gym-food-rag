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

    def test_cooked_vegetables_match_greens_family(self) -> None:
        candidates = [
            {
                "entity_id": "eggplant_1",
                "name": "Ca tim, luoc",
                "name_en": "Aubergine, boiled",
                "meal_family_key": "ca tim",
                "meal_role_tags": ["produce_support"],
            },
            {
                "entity_id": "longbean_1",
                "name": "Dau dua, luoc",
                "meal_family_key": "dau dua",
                "meal_role_tags": ["produce_support"],
            },
        ]

        for candidate in candidates:
            with self.subTest(candidate=candidate["entity_id"]):
                self.assertTrue(candidate_matches_benchmark_hint(candidate, "rau xanh"))
                self.assertEqual(candidate_equivalence_family_keys(candidate), ["greens_family"])

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
        corn_candidate = {
            "entity_id": "corn_1",
            "name": "Ngo, ca bap, nep, luoc",
            "name_en": "Corn on cob, boiled",
            "meal_family_key": "ngo nep",
            "meal_role_tags": ["carb_anchor"],
        }
        carrot_candidate = {
            "entity_id": "carrot_1",
            "name": "Ca rot, luoc",
            "name_en": "Carrot, boiled",
            "meal_family_key": "ca rot",
            "meal_role_tags": ["produce_support"],
        }
        buffalo_shank_candidate = {
            "entity_id": "buffalo_1",
            "name": "Thit trau bap, luoc",
            "meal_family_key": "thit trau bap",
            "meal_role_tags": ["protein_anchor"],
        }
        nem_chao_candidate = {
            "entity_id": "nem_1",
            "name": "Nem chao",
            "name_en": "Pork skin rolled with rice paper",
            "meal_family_key": "nem",
            "meal_role_tags": ["protein_anchor"],
        }

        self.assertEqual(candidate_equivalence_family_keys(rice_candidate), ["rice_family"])
        self.assertEqual(candidate_equivalence_family_keys(banana_candidate), ["fruit_family"])
        self.assertEqual(candidate_equivalence_family_keys(squid_candidate), ["id:squid_1"])
        self.assertEqual(candidate_equivalence_family_keys(corn_candidate), ["corn_family"])
        self.assertEqual(candidate_equivalence_family_keys(carrot_candidate), ["root_family"])
        self.assertEqual(
            candidate_equivalence_family_keys(buffalo_shank_candidate),
            ["id:buffalo_1"],
        )
        self.assertEqual(candidate_equivalence_family_keys(nem_chao_candidate), ["id:nem_1"])


if __name__ == "__main__":
    unittest.main()
