from sqlalchemy import text as sql_text
from app.db.schemas import users

async def seed_initial_data(engine, log_func=None):
    """
    Nạp dữ liệu khởi tạo.
    """
    async def log(msg):
        if log_func: await log_func(msg)

    with engine.begin() as conn:
        # Kiểm tra Admin
        if conn.execute(sql_text("SELECT count(*) FROM users WHERE username='admin'")).scalar() == 0:
            await log("[INFO] Seeding default admin account...")
            conn.execute(users.insert().values(
                username='admin', 
                password_hash='admin', # Thực tế nên hash!
                role='admin'
            ))
            await log("[SUCCESS] Admin created (user: admin / pass: admin).")
        else:
            await log("[INFO] Admin account already exists. Skipping.")