import asyncio
import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.db.tables import metadata, otp_requests, users
from app.services.auth import otp_service
from app.services.avatar_service import avatar_storage_service
from app.services.dashboard_overview_service import DashboardOverviewService
from app.services.nutrition.workflow.service import NutritionWorkflowService
from app.services.user_profile_contract import build_current_user_contract


class AuthOtpAvatarProfileTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.previous_otp_dev_mode = settings.OTP_DEV_MODE
        self.previous_avatar_max = settings.AVATAR_MAX_UPLOAD_BYTES
        settings.OTP_DEV_MODE = True
        settings.AVATAR_MAX_UPLOAD_BYTES = 32

    def tearDown(self):
        settings.OTP_DEV_MODE = self.previous_otp_dev_mode
        settings.AVATAR_MAX_UPLOAD_BYTES = self.previous_avatar_max

    def test_otp_request_verify_and_cooldown(self):
        db = self.Session()
        first = otp_service.request_otp(
            db,
            target="USER@example.com",
            channel="email",
            purpose="reset_password",
        )

        self.assertEqual(first["target"], "user@example.com")
        self.assertEqual(len(first["dev_code"]), 6)
        with self.assertRaises(ValueError):
            otp_service.request_otp(
                db,
                target="user@example.com",
                channel="email",
                purpose="reset_password",
            )

        verified = otp_service.verify_otp(
            db,
            otp_request_id=first["otp_request_id"],
            code=first["dev_code"],
        )
        self.assertIn("verification_token", verified)

    def test_otp_attempt_limit_counts_wrong_codes(self):
        db = self.Session()
        created = otp_service.request_otp(
            db,
            target="user@example.com",
            channel="email",
            purpose="reset_password",
        )

        with self.assertRaises(ValueError):
            otp_service.verify_otp(db, otp_request_id=created["otp_request_id"], code="000000")

        row = db.execute(
            select(otp_requests).where(otp_requests.c.id == created["otp_request_id"])
        ).mappings().one()
        self.assertEqual(row["attempt_count"], 1)

    def test_reset_password_uses_verification_token_and_clears_refresh_token(self):
        db = self.Session()
        db.execute(
            insert(users).values(
                username="demo",
                email="demo@example.com",
                password_hash=get_password_hash("old-password"),
                full_name="Demo",
                is_active=True,
                refresh_token="old-refresh",
            )
        )
        db.commit()
        created = otp_service.request_otp(
            db,
            target="demo@example.com",
            channel="email",
            purpose="reset_password",
        )
        verified = otp_service.verify_otp(
            db,
            otp_request_id=created["otp_request_id"],
            code=created["dev_code"],
        )

        otp_service.reset_password(
            db,
            verification_token=verified["verification_token"],
            new_password="new-password",
        )

        row = db.execute(select(users).where(users.c.email == "demo@example.com")).mappings().one()
        self.assertTrue(verify_password("new-password", row["password_hash"]))
        self.assertIsNone(row["refresh_token"])

    def test_avatar_accepts_image_and_rejects_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import app.services.avatar_service as avatar_module

            original_storage = avatar_module.STORAGE_DIR
            avatar_module.STORAGE_DIR = Path(tmpdir)
            try:
                avatar = UploadFile(
                    io.BytesIO(b"png-bytes"),
                    filename="avatar.png",
                    headers=Headers({"content-type": "image/png"}),
                )
                avatar_url = asyncio.run(
                    avatar_storage_service.save_user_avatar(user_id=7, file=avatar)
                )
                self.assertEqual(avatar_url, "/assets/avatars/7/avatar.png")
                self.assertTrue((Path(tmpdir) / "avatars" / "7" / "avatar.png").exists())

                bad_type = UploadFile(
                    io.BytesIO(b"abc"),
                    filename="bad.txt",
                    headers=Headers({"content-type": "text/plain"}),
                )
                with self.assertRaises(ValueError):
                    asyncio.run(avatar_storage_service.save_user_avatar(user_id=7, file=bad_type))

                large = UploadFile(
                    io.BytesIO(b"x" * 64),
                    filename="large.png",
                    headers=Headers({"content-type": "image/png"}),
                )
                with self.assertRaises(ValueError):
                    asyncio.run(avatar_storage_service.save_user_avatar(user_id=7, file=large))
            finally:
                avatar_module.STORAGE_DIR = original_storage

    def test_profile_update_normalizes_extended_fields(self):
        workflow = NutritionWorkflowService()
        normalized = workflow.normalize_profile_update(
            {
                "target_goal": "lose-fat",
                "dietary_preference": "balanced",
                "training_types": ["Gym", "Cardio", "Gym"],
                "medical_conditions": ["Không bệnh nền"],
                "favorite_meals": "cơm gà / bún bò",
            }
        )

        self.assertEqual(normalized["target_goal"], "lose_weight")
        self.assertEqual(normalized["dietary_preference"], "omnivore")
        self.assertEqual(normalized["training_types"], "Gym, Cardio")
        self.assertEqual(normalized["medical_conditions"], "Không bệnh nền")
        self.assertEqual(normalized["favorite_meals"], "cơm gà, bún bò")

    def test_build_profile_exposes_completion_contract(self):
        workflow = NutritionWorkflowService()
        profile = workflow.build_profile(
            {
                "id": 1,
                "username": "demo",
                "full_name": "Demo User",
                "age": 25,
                "gender": "male",
                "height": 170,
                "weight": 65,
                "activity_level": "active",
                "target_goal": "lose-fat",
            }
        )

        self.assertTrue(profile["is_profile_completed"])
        self.assertEqual(profile["target_goal"], "lose_weight")
        self.assertEqual(profile["goal_normalized_internal"], "lose_weight")
        self.assertEqual(profile["planning_strategy"], "deficit_high_satiety")

        legacy_profile = dict(profile)
        legacy_profile.pop("is_profile_completed")
        legacy_profile.pop("goal_normalized_internal")
        ensured_profile = workflow.ensure_profile_contract(legacy_profile)
        self.assertTrue(ensured_profile["is_profile_completed"])
        self.assertEqual(ensured_profile["goal_normalized_internal"], "lose_weight")

        incomplete = workflow.build_profile(
            {
                "id": 1,
                "username": "demo",
                "age": 25,
                "gender": "male",
                "height": 170,
                "activity_level": "active",
                "target_goal": "lose-fat",
            }
        )
        self.assertFalse(incomplete["is_profile_completed"])

    def test_current_user_contract_whitelists_and_merges_profile_fields(self):
        workflow = NutritionWorkflowService()
        current_user = {
            "id": 1,
            "username": "demo",
            "email": "demo@app.com",
            "password_hash": "must-not-leak",
            "full_name": "Demo User",
            "phone": "0900000000",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "age": 25,
            "gender": "male",
            "height": 170,
            "weight": 65,
            "activity_level": "active",
            "target_goal": "lose-fat",
        }

        profile = workflow.build_profile(current_user)
        payload = build_current_user_contract(
            current_user,
            permissions={"user.profile", "chat.use"},
            nutrition_profile=profile,
        )

        self.assertNotIn("password_hash", payload)
        self.assertEqual(payload["permissions"], ["chat.use", "user.profile"])
        self.assertTrue(payload["is_profile_completed"])
        self.assertEqual(payload["goal_normalized_internal"], "lose_weight")

    def test_dashboard_overview_uses_profile_without_recommendation_flow(self):
        service = DashboardOverviewService()
        overview = service.build_overview(
            {
                "id": 1,
                "username": "demo",
                "full_name": "Demo User",
                "age": 25,
                "gender": "male",
                "height": 170,
                "weight": 65,
                "activity_level": "active",
                "target_goal": "lose-fat",
            }
        )

        self.assertEqual(overview["greeting_name"], "Demo User")
        self.assertEqual(overview["goal_label"], "Giảm mỡ")
        self.assertTrue(overview["profile_completed"])
        self.assertEqual(overview["bmi"], 22.5)
        self.assertEqual(overview["bmr"], 1592.5)
        self.assertGreater(overview["calories_target"], 0)
        self.assertEqual(overview["macros"]["protein_g"], 130.0)
        self.assertEqual(overview["timeline"], [])
        self.assertEqual(overview["recent_plans"], [])

    def test_dashboard_overview_returns_safe_defaults_for_incomplete_profile(self):
        service = DashboardOverviewService()
        overview = service.build_overview(
            {
                "id": 1,
                "username": "demo",
                "full_name": "",
                "age": 25,
                "gender": "male",
                "height": 170,
                "activity_level": "active",
                "target_goal": "lose-fat",
            }
        )

        self.assertEqual(overview["greeting_name"], "demo")
        self.assertFalse(overview["profile_completed"])
        self.assertEqual(overview["calories_target"], 0.0)
        self.assertEqual(overview["calories_remaining"], 0.0)
        self.assertEqual(overview["macros"]["protein_g"], 0.0)
        self.assertIsNone(overview["bmi"])
        self.assertIsNone(overview["bmr"])


if __name__ == "__main__":
    unittest.main()
