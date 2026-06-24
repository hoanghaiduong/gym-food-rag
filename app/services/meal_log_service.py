from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from app.db.tables import meal_log_items, meal_logs
from app.schemas.meal_logs import MealLogCreate, MealLogItemCreate, MealLogUpdate


class MealLogService:
    def create(self, db: Session, *, user_id: int, payload: MealLogCreate) -> dict[str, Any]:
        totals = self._totals(payload.items)
        result = db.execute(
            insert(meal_logs).values(
                user_id=user_id,
                logged_at=payload.logged_at,
                meal_name=payload.meal_name,
                source=payload.source,
                notes=payload.notes,
                **totals,
            )
        )
        log_id = int(result.inserted_primary_key[0])
        self._insert_items(db, log_id=log_id, items=payload.items)
        db.commit()
        return self.get(db, user_id=user_id, log_id=log_id)

    def list(
        self,
        db: Session,
        *,
        user_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        rows = db.execute(self._base_query(user_id, date_from, date_to).order_by(meal_logs.c.logged_at.desc())).mappings()
        return [self._with_items(db, dict(row)) for row in rows]

    def get(self, db: Session, *, user_id: int, log_id: int) -> dict[str, Any]:
        row = db.execute(
            select(meal_logs).where(meal_logs.c.id == log_id, meal_logs.c.user_id == user_id)
        ).mappings().fetchone()
        if row is None:
            raise ValueError("Meal log not found.")
        return self._with_items(db, dict(row))

    def update(self, db: Session, *, user_id: int, log_id: int, payload: MealLogUpdate) -> dict[str, Any]:
        self.get(db, user_id=user_id, log_id=log_id)
        update_data = payload.model_dump(exclude_unset=True, exclude={"items"})
        if payload.items is not None:
            update_data.update(self._totals(payload.items))
        if update_data:
            db.execute(update(meal_logs).where(meal_logs.c.id == log_id).values(**update_data))
        if payload.items is not None:
            db.execute(delete(meal_log_items).where(meal_log_items.c.meal_log_id == log_id))
            self._insert_items(db, log_id=log_id, items=payload.items)
        db.commit()
        return self.get(db, user_id=user_id, log_id=log_id)

    def delete(self, db: Session, *, user_id: int, log_id: int) -> None:
        self.get(db, user_id=user_id, log_id=log_id)
        db.execute(delete(meal_log_items).where(meal_log_items.c.meal_log_id == log_id))
        db.execute(delete(meal_logs).where(meal_logs.c.id == log_id))
        db.commit()

    def summary(
        self,
        db: Session,
        *,
        user_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        query = self._base_query(user_id, date_from, date_to)
        logs = db.execute(query).mappings().all()
        log_ids = [row["id"] for row in logs]
        item_count = 0
        if log_ids:
            item_count = db.execute(
                select(func.count()).select_from(meal_log_items).where(meal_log_items.c.meal_log_id.in_(log_ids))
            ).scalar_one()
        return {
            "log_count": len(logs),
            "item_count": int(item_count or 0),
            "energy_kcal": round(sum(float(row["energy_kcal"] or 0) for row in logs), 2),
            "protein_g": round(sum(float(row["protein_g"] or 0) for row in logs), 2),
            "carbs_g": round(sum(float(row["carbs_g"] or 0) for row in logs), 2),
            "fat_g": round(sum(float(row["fat_g"] or 0) for row in logs), 2),
        }

    def _base_query(self, user_id: int, date_from: date | None, date_to: date | None):
        query = select(meal_logs).where(meal_logs.c.user_id == user_id)
        if date_from is not None:
            query = query.where(meal_logs.c.logged_at >= datetime.combine(date_from, time.min))
        if date_to is not None:
            query = query.where(meal_logs.c.logged_at <= datetime.combine(date_to, time.max))
        return query

    def _with_items(self, db: Session, row: dict[str, Any]) -> dict[str, Any]:
        rows = db.execute(
            select(meal_log_items).where(meal_log_items.c.meal_log_id == row["id"]).order_by(meal_log_items.c.id)
        ).mappings()
        row["items"] = [dict(item) for item in rows]
        return row

    def _insert_items(self, db: Session, *, log_id: int, items: list[MealLogItemCreate]) -> None:
        db.execute(
            insert(meal_log_items),
            [
                {
                    "meal_log_id": log_id,
                    **item.model_dump(),
                }
                for item in items
            ],
        )

    def _totals(self, items: list[MealLogItemCreate]) -> dict[str, float]:
        return {
            "energy_kcal": round(sum(float(item.energy_kcal or 0) for item in items), 2),
            "protein_g": round(sum(float(item.protein_g or 0) for item in items), 2),
            "carbs_g": round(sum(float(item.carbs_g or 0) for item in items), 2),
            "fat_g": round(sum(float(item.fat_g or 0) for item in items), 2),
        }


meal_log_service = MealLogService()
