from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Table, Text, func

from app.db.base import metadata


meal_logs = Table(
    "meal_logs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("logged_at", DateTime, nullable=False),
    Column("meal_name", String(100), nullable=False),
    Column("source", String(30), nullable=False, default="manual"),
    Column("energy_kcal", Float, nullable=False, default=0.0),
    Column("protein_g", Float, nullable=False, default=0.0),
    Column("carbs_g", Float, nullable=False, default=0.0),
    Column("fat_g", Float, nullable=False, default=0.0),
    Column("notes", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)


meal_log_items = Table(
    "meal_log_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("meal_log_id", Integer, ForeignKey("meal_logs.id"), nullable=False),
    Column("entity_id", String(100), nullable=True),
    Column("food_id", String(100), nullable=True),
    Column("display_name", String(255), nullable=False),
    Column("grams", Float, nullable=False, default=0.0),
    Column("energy_kcal", Float, nullable=False, default=0.0),
    Column("protein_g", Float, nullable=False, default=0.0),
    Column("carbs_g", Float, nullable=False, default=0.0),
    Column("fat_g", Float, nullable=False, default=0.0),
    Column("created_at", DateTime, server_default=func.now()),
)


workout_logs = Table(
    "workout_logs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("logged_at", DateTime, nullable=False),
    Column("workout_type", String(100), nullable=False),
    Column("duration_minutes", Integer, nullable=False, default=0),
    Column("intensity", String(30), nullable=False, default="moderate"),
    Column("calories_estimated", Float, nullable=False, default=0.0),
    Column("notes", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)


workout_log_exercises = Table(
    "workout_log_exercises",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("workout_log_id", Integer, ForeignKey("workout_logs.id"), nullable=False),
    Column("exercise_name", String(255), nullable=False),
    Column("sets", Integer, nullable=True),
    Column("reps", String(50), nullable=True),
    Column("weight_kg", Float, nullable=True),
    Column("duration_minutes", Integer, nullable=True),
    Column("rest_seconds", Integer, nullable=True),
    Column("notes", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
)


saved_plans = Table(
    "saved_plans",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("plan_type", String(30), nullable=False),
    Column("date_from", Date, nullable=True),
    Column("date_to", Date, nullable=True),
    Column("title", String(255), nullable=True),
    Column("status", String(30), nullable=False, default="active"),
    Column("payload_json", Text, nullable=False),
    Column("source_request_json", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)
