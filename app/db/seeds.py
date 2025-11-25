from sqlalchemy import text as sql_text
from app.db.schemas import users

async def seed_initial_data(engine, log_func=None):
    """
    Nạp dữ liệu hệ thống (Chỉ nạp settings hoặc data tĩnh, KHÔNG tạo user nữa).
    """
    async def log(msg):
        if log_func: await log_func(msg)

    # Ở đây chúng ta không tạo user 'admin' nữa
    # Vì User sẽ được tạo thủ công qua giao diện ở bước tiếp theo
    await log("[INFO] Database tables ready. Waiting for Admin creation via UI...")