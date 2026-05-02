import asyncio
import unittest

from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker

from app.db.tables import metadata, users
from app.modules.users.router import get_my_preferences, update_my_preferences
from app.schemas.users import UserPreferencesUpdate


class UserPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.execute(
            insert(users).values(
                id=1,
                username="demo",
                email="demo@example.com",
                password_hash="hash",
                full_name="Demo",
                is_active=True,
            )
        )
        self.db.commit()
        self.current_user = self.db.execute(users.select().where(users.c.id == 1)).mappings().one()

    def tearDown(self):
        self.db.close()

    def test_preferences_defaults_when_user_has_no_settings(self):
        response = asyncio.run(get_my_preferences(current_user=self.current_user))

        self.assertEqual(response["data"]["language"], "vi")
        self.assertEqual(response["data"]["theme"], "system")
        self.assertFalse(response["data"]["biometric_unlock_enabled"])

    def test_update_preferences_allows_false_values(self):
        response = asyncio.run(
            update_my_preferences(
                UserPreferencesUpdate(
                    language="en",
                    theme="dark",
                    push_notifications=True,
                    biometric_unlock_enabled=False,
                ),
                db=self.db,
                current_user=self.current_user,
            )
        )

        self.assertEqual(response["data"]["language"], "en")
        self.assertEqual(response["data"]["theme"], "dark")
        self.assertTrue(response["data"]["push_notifications"])
        self.assertFalse(response["data"]["biometric_unlock_enabled"])


if __name__ == "__main__":
    unittest.main()
