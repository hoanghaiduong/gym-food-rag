import os
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "gym-food-super-admin")

async def verify_admin(x_admin_key: str = Header(...)):
    """Dependency dùng chung cho tất cả API Admin"""
    if x_admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="❌ Không có quyền truy cập Admin!")