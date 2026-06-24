from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.db.tables import saved_plans
from app.schemas.nutrition import NutritionRecommendationRequest
from app.schemas.saved_plans import (
    MonthlyPlanGenerateRequest,
    SavedPlanCreate,
    SavedPlanUpdate,
    WeeklyPlanGenerateRequest,
)
from app.schemas.training import TrainingRecommendationRequest
from app.services._json_store import dumps_json, loads_json
from app.services.plans_service import plans_service
from app.services.training_plan_service import training_plan_service


class PlanPersistenceService:
    def create(self, db: Session, *, user_id: int, payload: SavedPlanCreate) -> dict[str, Any]:
        self._validate_payload(payload.plan_type, payload.payload)
        result = db.execute(
            insert(saved_plans).values(
                user_id=user_id,
                plan_type=payload.plan_type,
                title=payload.title,
                date_from=payload.date_from,
                date_to=payload.date_to,
                status=payload.status,
                payload_json=dumps_json(payload.payload),
                source_request_json=dumps_json(payload.source_request),
            )
        )
        plan_id = int(result.inserted_primary_key[0])
        db.commit()
        return self.get(db, user_id=user_id, plan_id=plan_id)

    def list(
        self,
        db: Session,
        *,
        user_id: int,
        plan_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        query = select(saved_plans).where(saved_plans.c.user_id == user_id)
        if plan_type:
            query = query.where(saved_plans.c.plan_type == plan_type)
        if date_from:
            query = query.where(saved_plans.c.date_to >= date_from)
        if date_to:
            query = query.where(saved_plans.c.date_from <= date_to)
        rows = db.execute(query.order_by(saved_plans.c.date_from.desc(), saved_plans.c.id.desc())).mappings()
        return [self._decode(dict(row)) for row in rows]

    def get(self, db: Session, *, user_id: int, plan_id: int) -> dict[str, Any]:
        row = db.execute(
            select(saved_plans).where(saved_plans.c.id == plan_id, saved_plans.c.user_id == user_id)
        ).mappings().fetchone()
        if row is None:
            raise ValueError("Saved plan not found.")
        return self._decode(dict(row))

    def update(self, db: Session, *, user_id: int, plan_id: int, payload: SavedPlanUpdate) -> dict[str, Any]:
        existing = self.get(db, user_id=user_id, plan_id=plan_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "payload" in update_data:
            self._validate_payload(existing["plan_type"], update_data["payload"])
            update_data["payload_json"] = dumps_json(update_data.pop("payload"))
        if "source_request" in update_data:
            update_data["source_request_json"] = dumps_json(update_data.pop("source_request"))
        if update_data:
            db.execute(update(saved_plans).where(saved_plans.c.id == plan_id).values(**update_data))
            db.commit()
        return self.get(db, user_id=user_id, plan_id=plan_id)

    def delete(self, db: Session, *, user_id: int, plan_id: int) -> None:
        self.get(db, user_id=user_id, plan_id=plan_id)
        db.execute(delete(saved_plans).where(saved_plans.c.id == plan_id))
        db.commit()

    def generate_weekly(
        self,
        db: Session,
        *,
        current_user: dict[str, Any],
        payload: WeeklyPlanGenerateRequest,
    ) -> dict[str, Any]:
        start_day = payload.week_start or plans_service._start_of_week(plans_service._today())
        end_day = start_day + timedelta(days=6)
        source_request = payload.model_dump(mode="json")
        generated = self._build_generated_payload(
            current_user=current_user,
            nutrition_request=payload.nutrition_request,
            training_request=payload.training_request,
            include_nutrition=payload.include_nutrition,
            include_training=payload.include_training,
        )
        weekly_timeline = plans_service.build_weekly(current_user, week_start=start_day)
        generated.update({"weekly_timeline": weekly_timeline})
        return self.create(
            db,
            user_id=int(current_user["id"]),
            payload=SavedPlanCreate(
                plan_type="weekly",
                title=payload.title or f"Kế hoạch tuần {start_day.isoformat()}",
                date_from=start_day,
                date_to=end_day,
                payload=generated,
                source_request=source_request,
            ),
        )

    def generate_monthly(
        self,
        db: Session,
        *,
        current_user: dict[str, Any],
        payload: MonthlyPlanGenerateRequest,
    ) -> dict[str, Any]:
        start_day = date(payload.year, payload.month, 1)
        end_day = date(payload.year, payload.month, calendar.monthrange(payload.year, payload.month)[1])
        source_request = payload.model_dump(mode="json")
        generated = self._build_generated_payload(
            current_user=current_user,
            nutrition_request=payload.nutrition_request,
            training_request=payload.training_request,
            include_nutrition=payload.include_nutrition,
            include_training=payload.include_training,
        )
        generated.update({"monthly_overview": plans_service.build_monthly(current_user, year=payload.year, month=payload.month)})
        return self.create(
            db,
            user_id=int(current_user["id"]),
            payload=SavedPlanCreate(
                plan_type="monthly",
                title=payload.title or f"Kế hoạch tháng {payload.month}/{payload.year}",
                date_from=start_day,
                date_to=end_day,
                payload=generated,
                source_request=source_request,
            ),
        )

    def get_weekly_timeline(self, db: Session, *, user_id: int, week_start: date) -> list[dict[str, Any]] | None:
        plan = self._latest_plan(db, user_id=user_id, plan_type="weekly", date_from=week_start, date_to=week_start + timedelta(days=6))
        if not plan:
            return None
        timeline = plan["payload"].get("weekly_timeline")
        return timeline if isinstance(timeline, list) else None

    def get_monthly_overview(self, db: Session, *, user_id: int, year: int, month: int) -> dict[str, Any] | None:
        start_day = date(year, month, 1)
        end_day = date(year, month, calendar.monthrange(year, month)[1])
        plan = self._latest_plan(db, user_id=user_id, plan_type="monthly", date_from=start_day, date_to=end_day)
        if not plan:
            return None
        overview = plan["payload"].get("monthly_overview")
        return overview if isinstance(overview, dict) else None

    def _latest_plan(
        self,
        db: Session,
        *,
        user_id: int,
        plan_type: str,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any] | None:
        row = db.execute(
            select(saved_plans)
            .where(
                saved_plans.c.user_id == user_id,
                saved_plans.c.plan_type == plan_type,
                saved_plans.c.status == "active",
                saved_plans.c.date_from == date_from,
                saved_plans.c.date_to == date_to,
            )
            .order_by(saved_plans.c.id.desc())
        ).mappings().fetchone()
        return self._decode(dict(row)) if row else None

    def _build_generated_payload(
        self,
        *,
        current_user: dict[str, Any],
        nutrition_request: NutritionRecommendationRequest | None,
        training_request: TrainingRecommendationRequest | None,
        include_nutrition: bool,
        include_training: bool,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"nutrition_template": None, "training_template": None}
        if include_nutrition:
            from app.services.nutrition_workflow_service import nutrition_workflow_service

            request = nutrition_request or NutritionRecommendationRequest(use_cache=False, include_debug=False)
            nutrition = nutrition_workflow_service.run_main_flow(current_user, request)
            self._validate_nutrition_snapshot(nutrition)
            result["nutrition_template"] = nutrition
        if include_training:
            request = training_request or TrainingRecommendationRequest()
            result["training_template"] = training_plan_service.build_recommendation(current_user, request)
        return result

    def _validate_payload(self, plan_type: str, payload: dict[str, Any]) -> None:
        if plan_type == "nutrition":
            self._validate_nutrition_snapshot(payload)

    def _validate_nutrition_snapshot(self, payload: dict[str, Any]) -> None:
        validation = payload.get("validation") or {}
        if not validation.get("passed"):
            raise ValueError("Cannot save a nutrition plan that did not pass validation.")
        if int(validation.get("unsafe_raw_output_count") or 0) or int(validation.get("unsafe_label_count") or 0):
            raise ValueError("Cannot save a nutrition plan with unsafe output.")

    def _decode(self, row: dict[str, Any]) -> dict[str, Any]:
        row["payload"] = loads_json(row.pop("payload_json"), {})
        row["source_request"] = loads_json(row.pop("source_request_json"), None)
        return row


plan_persistence_service = PlanPersistenceService()
