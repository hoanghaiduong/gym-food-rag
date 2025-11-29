# app/core/redis.py
import redis.asyncio as redis
from app.core.config import settings

# Tạo connection pool để tái sử dụng kết nối (Quan trọng cho Scalability)
redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST, 
    port=settings.REDIS_PORT, 
    db=0, 
    decode_responses=True
)

# Hàm lấy client (dùng trong Dependency)
async def get_redis():
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close()