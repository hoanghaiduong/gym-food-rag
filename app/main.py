from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

# Import các router
# from app.api.v3 import chat_v3, rbac
from app.api.v3 import rbac
from app.modules.users import controller as users_controller
from app.core.config import settings
# from app.api.v1 import chat
from app.api.v2 import admin, history, system, setup, users, auth
from app.api.v3 import  auth as auth_v3
# from app.services.v3.agent import agent_service_v3
from app.core.exceptions import add_exception_handlers

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("app.log", encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 System starting up...")
    log_task = asyncio.create_task(system.watch_log_file())
    # 1. Code chạy khi Server KHỞI ĐỘNG
    try:
        # await agent_service_v3.initialize() # <--- Gọi hàm tạo Index Redis
        pass
    except Exception as e:
        print(f"❌ Lỗi khởi tạo Redis Index: {e}")
    yield
    logger.info("🛑 System shutting down...")
    log_task.cancel()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Add Global Exception Handlers
add_exception_handlers(app)

# ... (Phần CORS và Router giữ nguyên) ...
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(setup.router, prefix="/api/v2/setup", tags=["Setup Wizard"])
# app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["Chat V1 (Legacy)"])
# app.include_router(chat_v2.router, prefix="/api/v2", tags=["Chat V2 (Hybrid)"])
# app.include_router(admin.router, prefix="/api/v2/admin", tags=["Admin Data"])
app.include_router(system.router, prefix="/api/v2/system", tags=["System Control"])
# app.include_router(auth.router, prefix="/api/v2/auth", tags=["Authentication"])
# app.include_router(users.router, prefix="/api/v2/users", tags=["Admin User Management"])
# app.include_router(history.router, prefix="/api/v2/history", tags=["User History"])
# app.include_router(chat_v3.router, prefix="/api/v3", tags=["Chat V3 (LangGraph Agent)"]) # [MỚI]
app.include_router(auth_v3.router, prefix="/api/v3/auth", tags=["Authentication V3 (RBAC)"])
app.include_router(rbac.router, prefix="/api/v3/rbac", tags=["V3 Access Control (RBAC)"])
app.include_router(users_controller.router, prefix="/api/v3/users", tags=["V3 User Management"])
@app.get("/")
def root():
    return {"message": "API is running!"}

