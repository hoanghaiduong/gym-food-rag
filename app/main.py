from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware # <--- BỔ SUNG IMPORT NÀY
import asyncio
import logging

# Import các router và module system
from app.core.config import settings
from app.api.v1 import chat
from app.api.v2 import chat_v2, admin, system, setup

# --- CẤU HÌNH LOGGER (Để module system đọc được file log) ---
# Encoding utf-8 để tránh lỗi khi log tiếng Việt trên Windows
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding='utf-8'), 
        logging.StreamHandler()
    ]
)

# --- LIFESPAN HANDLER (Quản lý vòng đời ứng dụng) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. STARTUP
    print("🚀 System starting up...")
    
    # Kích hoạt task đọc log chạy ngầm
    # system.watch_log_file() là hàm async chúng ta đã viết trong system.py
    log_task = asyncio.create_task(system.watch_log_file())
    print("👀 Log Watcher started!")
    
    yield # Server bắt đầu phục vụ request tại đây
    
    # 2. SHUTDOWN
    print("🛑 System shutting down...")
    log_task.cancel()
    try:
        await log_task
    except asyncio.CancelledError:
        print("✅ Log Watcher stopped gracefully.")

# --- KHỞI TẠO APP ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# --- [QUAN TRỌNG] CẤU HÌNH CORS ---
# Cho phép Frontend (thường chạy ở port khác, vd: 3000) gọi API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong môi trường Dev, để "*" là tiện nhất
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ĐĂNG KÝ ROUTER ---
app.include_router(setup.router, prefix="/api/v2/setup", tags=["Setup Wizard"])
app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["Chat V1 (Legacy)"])
app.include_router(chat_v2.router, prefix="/api/v2", tags=["Chat V2 (Hybrid)"])
app.include_router(admin.router, prefix="/api/v2/admin", tags=["Admin Data"])
app.include_router(system.router, prefix="/api/v2/system", tags=["System Control"])

@app.get("/")
def root():
    return {"message": "Gym Food Recommendation API is running!"}