from sqlalchemy import create_engine, text as sql_text
from app.db.schemas import metadata

async def run_db_migrations(engine, force_reset: bool = False, log_func=None):
    """
    Thực hiện quy trình tạo bảng.
    """
    async def log(msg):
        if log_func: await log_func(msg)

    if force_reset:
        await log("[WARN] User requested FORCE RESET. Dropping schema 'public'...")
        with engine.connect() as conn:
            conn.execute(sql_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()
        await log("[SUCCESS] Schema cleaned.")

    await log("[INFO] Creating tables...")
    # Tạo tất cả bảng đã định nghĩa trong schema.py
    metadata.create_all(engine)
    await log("[SUCCESS] All tables created successfully.")