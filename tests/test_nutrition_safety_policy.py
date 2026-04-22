from __future__ import annotations

import unittest
from pathlib import Path

from app.services.nutrition_knowledge_service import build_vector_payload
from app.services.nutrition_record_policy import (
    CONSUMPTION_STATE_DIRECT_EDIBLE_RAW,
    CONSUMPTION_STATE_REQUIRES_PREPARATION,
    enrich_meal_ready_record,
    meal_family_key,
)


class NutritionSafetyPolicyTests(unittest.TestCase):
    def test_raw_turkey_requires_preparation(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_turkey_raw",
                "entity_type": "food",
                "name": "Thit ga tay, tuoi",
                "group_name": "Thit gia cam",
                "taxonomy_level_1": "protein_foods",
                "taxonomy_level_2": "meats",
                "energy_kcal": 114,
                "protein_g": 23.0,
                "carbs_g": 0.0,
                "fat_g": 1.6,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])
        self.assertEqual(record["unsafe_output_reason"], "raw_animal_protein")
        self.assertFalse(record["production_retrieval_enabled"])

    def test_raw_corn_requires_preparation(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_corn_raw",
                "entity_type": "food",
                "name": "Ngo, ca bap, tuoi",
                "group_name": "Ngu coc",
                "taxonomy_level_1": "plant_foods",
                "taxonomy_level_2": "grains",
                "energy_kcal": 96,
                "protein_g": 3.4,
                "carbs_g": 21.0,
                "fat_g": 1.5,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])
        self.assertEqual(record["unsafe_output_reason"], "raw_starchy_staple")

    def test_bun_tuoi_is_allowed_direct_edible(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_bun_tuoi",
                "entity_type": "food",
                "name": "Bun tuoi",
                "group_name": "Ngu coc",
                "taxonomy_level_1": "plant_foods",
                "taxonomy_level_2": "noodles",
                "energy_kcal": 110,
                "protein_g": 1.7,
                "carbs_g": 25.0,
                "fat_g": 0.2,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_DIRECT_EDIBLE_RAW)
        self.assertTrue(record["final_output_allowed"])
        self.assertEqual(record["safe_display_name"], "Bun tuoi")

    def test_ambiguous_raw_produce_is_blocked(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_cu_nieng_raw",
                "entity_type": "food",
                "name": "Cu nieng, tuoi",
                "group_name": "Rau cu",
                "taxonomy_level_1": "vegetables",
                "taxonomy_level_2": "produce",
                "energy_kcal": 17,
                "protein_g": 0.8,
                "carbs_g": 3.1,
                "fat_g": 0.1,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])
        self.assertEqual(record["unsafe_output_reason"], "raw_ambiguous_ingredient")

    def test_raw_rau_diep_is_blocked(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_rau_diep_raw",
                "entity_type": "food",
                "name": "Rau diep, tuoi",
                "group_name": "Rau cu",
                "taxonomy_level_1": "vegetables",
                "taxonomy_level_2": "produce",
                "energy_kcal": 15,
                "protein_g": 1.4,
                "carbs_g": 2.9,
                "fat_g": 0.2,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])

    def test_raw_tomato_is_blocked(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_ca_chua_raw",
                "entity_type": "food",
                "name": "Ca chua, tuoi",
                "group_name": "Rau cu",
                "taxonomy_level_1": "vegetables",
                "taxonomy_level_2": "produce",
                "energy_kcal": 18,
                "protein_g": 0.9,
                "carbs_g": 3.9,
                "fat_g": 0.2,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])

    def test_raw_cucumber_is_blocked(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_dua_leo_raw",
                "entity_type": "food",
                "name": "Dua leo, tuoi",
                "group_name": "Rau cu",
                "taxonomy_level_1": "vegetables",
                "taxonomy_level_2": "produce",
                "energy_kcal": 15,
                "protein_g": 0.7,
                "carbs_g": 3.6,
                "fat_g": 0.1,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])

    def test_raw_lotus_seed_is_blocked(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_hat_sen_raw",
                "entity_type": "food",
                "name": "Hat sen, tuoi",
                "group_name": "Ngu coc",
                "taxonomy_level_1": "plant_foods",
                "taxonomy_level_2": "grains",
                "energy_kcal": 89,
                "protein_g": 4.0,
                "carbs_g": 17.0,
                "fat_g": 0.5,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])

    def test_family_keys_align_raw_and_safe_variants(self) -> None:
        self.assertEqual(meal_family_key("Ngo, ca bap, tuoi"), meal_family_key("Ngo luoc"))
        self.assertEqual(meal_family_key("Thit ga tay, tuoi"), meal_family_key("Uc ga luoc"))

    def test_enriched_record_carries_safety_fields(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_payload",
                "entity_type": "food",
                "name": "Thit ga tay, tuoi",
                "group_name": "Thit gia cam",
                "taxonomy_level_1": "protein_foods",
                "taxonomy_level_2": "meats",
                "energy_kcal": 114,
                "protein_g": 23.0,
                "carbs_g": 0.0,
                "fat_g": 1.6,
            }
        )
        self.assertIn("consumption_state", record)
        self.assertIn("final_output_allowed", record)
        self.assertIn("unsafe_output_reason", record)
        self.assertIn("safe_display_name", record)
        self.assertFalse(record["final_output_allowed"])

    def test_payload_builder_blocks_stale_raw_ingest_flags(self) -> None:
        payload = build_vector_payload(
            {
                "entity_id": "food_test_stale_flag",
                "entity_type": "food",
                "name": "Gia dau tuong, tuoi",
                "group_name": "Rau, qua, cu dung lam rau",
                "taxonomy_level_1": "vegetables",
                "taxonomy_level_2": "produce",
                "energy_kcal": 43,
                "protein_g": 5.1,
                "carbs_g": 4.5,
                "fat_g": 0.6,
                "qdrant_ingest_eligible": True,
                "retrieval_enabled": True,
                "production_retrieval_enabled": True,
            }
        )
        self.assertEqual(payload["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(payload["final_output_allowed"])
        self.assertFalse(payload["qdrant_ingest_eligible"])
        self.assertFalse(payload["retrieval_enabled"])
        self.assertFalse(payload["production_retrieval_enabled"])

    def test_raw_vegetable_names_do_not_fake_cooked_state(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_rau_khoai_raw",
                "entity_type": "food",
                "name": "Rau khoai lang, tuoi",
                "group_name": "Rau, qua, cu dung lam rau",
                "taxonomy_level_1": "vegetables",
                "taxonomy_level_2": "produce",
                "energy_kcal": 32,
                "protein_g": 3.0,
                "carbs_g": 5.5,
                "fat_g": 0.4,
            }
        )
        self.assertEqual(record["consumption_state"], CONSUMPTION_STATE_REQUIRES_PREPARATION)
        self.assertFalse(record["final_output_allowed"])

    def test_cooked_safe_display_name_drops_raw_marker(self) -> None:
        record = enrich_meal_ready_record(
            {
                "entity_id": "food_test_cooked_corn",
                "entity_type": "food",
                "name": "Ngo tuoi, nep, nuong",
                "group_name": "Ngu coc va san pham che bien",
                "taxonomy_level_1": "plant_foods",
                "taxonomy_level_2": "grains",
                "energy_kcal": 128,
                "protein_g": 3.8,
                "carbs_g": 26.0,
                "fat_g": 1.6,
            }
        )
        self.assertEqual(record["consumption_state"], "prepared_ready")
        self.assertNotIn("tuoi", record["safe_display_name"].lower())

    def test_unsafe_composite_query_removed(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "services"
            / "nutrition"
            / "workflow"
            / "retrieval_queries.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("thit ga bun tuoi", source)


if __name__ == "__main__":
    unittest.main()
