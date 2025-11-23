from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

# Import các router và module system
from app.core.config import settings
from app.api.v1 import chat
from app.api.v2 import chat_v2, admin, system ,setup

# --- CẤU HÌNH LOGGER (Để module system đọc được file log) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"), # Ghi ra file
        logging.StreamHandler()         # Hiện ra terminal
    ]
)

# --- LIFESPAN HANDLER (Thay thế cho @app.on_event) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. CODE CHẠY KHI SERVER KHỞI ĐỘNG (STARTUP)
    print("🚀 System starting up...")
    
    # Tạo task chạy ngầm đọc log (Fire & Forget)
    # Chúng ta giữ tham chiếu 'task' để có thể hủy nó khi tắt server
    log_task = asyncio.create_task(system.watch_log_file())
    print("👀 Log Watcher started!")
    
    yield # Điểm ngăn cách: Server bắt đầu nhận request tại đây
    
    # 2. CODE CHẠY KHI SERVER TẮT (SHUTDOWN)
    print("🛑 System shutting down...")
    # Hủy task đọc log để tránh treo background process
    log_task.cancel()
    try:
        await log_task
    except asyncio.CancelledError:
        print("✅ Log Watcher stopped gracefully.")

# --- KHỞI TẠO APP VỚI LIFESPAN ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan  # <--- Truyền hàm lifespan vào đây
)

# Include router
app.include_router(setup.router, prefix="/api/v2/setup", tags=["Setup Wizard"])
app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["Chat V1 (Legacy)"])
app.include_router(chat_v2.router, prefix="/api/v2", tags=["Chat V2 (Hybrid)"])
app.include_router(admin.router, prefix="/api/v2/admin", tags=["Admin Data"])
app.include_router(system.router, prefix="/api/v2/system", tags=["System Control"])

@app.get("/")
def root():
    return {"message": "Gym Food Recommendation API is running!"}