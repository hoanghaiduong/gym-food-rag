from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from app.db.tables import workout_log_exercises, workout_logs
from app.schemas.workout_logs import WorkoutExerciseCreate, WorkoutLogCreate, WorkoutLogUpdate


class WorkoutLogService:
    def create(self, db: Session, *, user_id: int, payload: WorkoutLogCreate) -> dict[str, Any]:
        result = db.execute(
            insert(workout_logs).values(
                user_id=user_id,
                logged_at=payload.logged_at,
                workout_type=payload.workout_type,
                duration_minutes=payload.duration_minutes,
                intensity=payload.intensity,
                calories_estimated=payload.calories_estimated,
                notes=payload.notes,
            )
        )
        log_id = int(result.inserted_primary_key[0])
        self._insert_exercises(db, log_id=log_id, exercises=payload.exercises)
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
        rows = db.execute(self._base_query(user_id, date_from, date_to).order_by(workout_logs.c.logged_at.desc())).mappings()
        return [self._with_exercises(db, dict(row)) for row in rows]

    def get(self, db: Session, *, user_id: int, log_id: int) -> dict[str, Any]:
        row = db.execute(
            select(workout_logs).where(workout_logs.c.id == log_id, workout_logs.c.user_id == user_id)
        ).mappings().fetchone()
        if row is None:
            raise ValueError("Workout log not found.")
        return self._with_exercises(db, dict(row))

    def update(self, db: Session, *, user_id: int, log_id: int, payload: WorkoutLogUpdate) -> dict[str, Any]:
        self.get(db, user_id=user_id, log_id=log_id)
        update_data = payload.model_dump(exclude_unset=True, exclude={"exercises"})
        if update_data:
            db.execute(update(workout_logs).where(workout_logs.c.id == log_id).values(**update_data))
        if payload.exercises is not None:
            db.execute(delete(workout_log_exercises).where(workout_log_exercises.c.workout_log_id == log_id))
            self._insert_exercises(db, log_id=log_id, exercises=payload.exercises)
        db.commit()
        return self.get(db, user_id=user_id, log_id=log_id)

    def delete(self, db: Session, *, user_id: int, log_id: int) -> None:
        self.get(db, user_id=user_id, log_id=log_id)
        db.execute(delete(workout_log_exercises).where(workout_log_exercises.c.workout_log_id == log_id))
        db.execute(delete(workout_logs).where(workout_logs.c.id == log_id))
        db.commit()

    def summary(
        self,
        db: Session,
        *,
        user_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        logs = db.execute(self._base_query(user_id, date_from, date_to)).mappings().all()
        log_ids = [row["id"] for row in logs]
        exercise_count = 0
        if log_ids:
            exercise_count = db.execute(
                select(func.count()).select_from(workout_log_exercises).where(workout_log_exercises.c.workout_log_id.in_(log_ids))
            ).scalar_one()
        return {
            "log_count": len(logs),
            "exercise_count": int(exercise_count or 0),
            "duration_minutes": int(sum(int(row["duration_minutes"] or 0) for row in logs)),
            "calories_estimated": round(sum(float(row["calories_estimated"] or 0) for row in logs), 2),
        }

    def _base_query(self, user_id: int, date_from: date | None, date_to: date | None):
        query = select(workout_logs).where(workout_logs.c.user_id == user_id)
        if date_from is not None:
            query = query.where(workout_logs.c.logged_at >= datetime.combine(date_from, time.min))
        if date_to is not None:
            query = query.where(workout_logs.c.logged_at <= datetime.combine(date_to, time.max))
        return query

    def _with_exercises(self, db: Session, row: dict[str, Any]) -> dict[str, Any]:
        rows = db.execute(
            select(workout_log_exercises)
            .where(workout_log_exercises.c.workout_log_id == row["id"])
            .order_by(workout_log_exercises.c.id)
        ).mappings()
        row["exercises"] = [dict(item) for item in rows]
        return row

    def _insert_exercises(self, db: Session, *, log_id: int, exercises: list[WorkoutExerciseCreate]) -> None:
        if not exercises:
            return
        db.execute(
            insert(workout_log_exercises),
            [{"workout_log_id": log_id, **exercise.model_dump()} for exercise in exercises],
        )


workout_log_service = WorkoutLogService()
