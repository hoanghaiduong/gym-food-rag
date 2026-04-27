import unittest

from app.services.nutrition.knowledge.diet_compatibility import (
    effective_diet_tags,
    matches_dietary_preference,
)
from app.services.nutrition.knowledge.tags import derive_diet_tags


class DietCompatibilityTests(unittest.TestCase):
    def test_nuts_are_inferred_as_vegan_and_vegetarian(self):
        payload = {"name": "Hạt bí đỏ, rang", "diet_tags": ["high_protein"]}

        tags = effective_diet_tags(payload)

        self.assertIn("vegan", tags)
        self.assertIn("vegetarian", tags)
        self.assertTrue(matches_dietary_preference("vegan", payload["diet_tags"], payload))
        self.assertTrue(matches_dietary_preference("vegetarian", payload["diet_tags"], payload))

    def test_yogurt_is_inferred_as_vegetarian_not_vegan(self):
        payload = {"name": "Sữa chua", "diet_tags": ["low_fat"]}

        tags = effective_diet_tags(payload)

        self.assertIn("vegetarian", tags)
        self.assertNotIn("vegan", tags)
        self.assertTrue(matches_dietary_preference("vegetarian", payload["diet_tags"], payload))
        self.assertFalse(matches_dietary_preference("vegan", payload["diet_tags"], payload))

    def test_fish_name_does_not_match_peanut_marker(self):
        payload = {"name": "Cá lác, luộc", "diet_tags": ["pescatarian"]}

        tags = effective_diet_tags(payload)

        self.assertIn("pescatarian", tags)
        self.assertNotIn("vegetarian", tags)
        self.assertFalse(matches_dietary_preference("vegetarian", payload["diet_tags"], payload))

    def test_plain_tofu_derives_vegan_and_vegetarian_tags(self):
        record = {
            "name": "Dau phu luoc",
            "name_en": "Tofu boiled",
            "group_name": "",
            "protein_g": 10,
            "fat_g": 5,
            "carbs_g": 2,
        }

        tags = derive_diet_tags(record, ["soy"])

        self.assertIn("vegan", tags)
        self.assertIn("vegetarian", tags)


if __name__ == "__main__":
    unittest.main()
