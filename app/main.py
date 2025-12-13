from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from sqlalchemy.exc import OperationalError, SQLAlchemyError

# Import các router
from app.api.v3 import chat_v3, rbac,users as users_v3
from app.core.config import settings
# from app.api.v1 import chat
from app.api.v2 import chat_v2, admin, history, system, setup, users, auth

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
    yield
    logger.info("🛑 System shutting down...")
    log_task.cancel()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# =================================================================
# 🔥 UNIFIED EXCEPTION HANDLER (QUẢN LÝ LỖI TẬP TRUNG)
# =================================================================

def create_error_response(status_code: int, message: str, detail: str = None):
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "code": status_code,
            "message": message,
            "detail": detail
        },
    )

# 1. Bắt lỗi HTTP do bạn tự raise (HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return create_error_response(exc.status_code, exc.detail)

# 2. Bắt lỗi Validate dữ liệu (Pydantic - 422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Lấy chi tiết lỗi đầu tiên cho gọn
    error_msg = exc.errors()[0].get("msg") if exc.errors() else "Invalid data"
    return create_error_response(422, "Dữ liệu đầu vào không hợp lệ", str(exc.errors()))

# 3. Bắt lỗi Kết nối Database (503)
@app.exception_handler(OperationalError)
async def db_connection_handler(request: Request, exc: OperationalError):
    logger.error(f"DB Connection Failed: {exc}")
    return create_error_response(503, "Không thể kết nối cơ sở dữ liệu. Hệ thống đang bảo trì.")

# 4. Bắt lỗi SQL chung (500)
@app.exception_handler(SQLAlchemyError)
async def db_query_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"SQL Error: {exc}")
    return create_error_response(500, "Lỗi truy vấn dữ liệu.")

# 5. Bắt tất cả lỗi không xác định còn lại (500)
@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Error: {exc}", exc_info=True)
    return create_error_response(500, "Lỗi hệ thống nội bộ.", str(exc))

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
app.include_router(admin.router, prefix="/api/v2/admin", tags=["Admin Data"])
# app.include_router(system.router, prefix="/api/v2/system", tags=["System Control"])
app.include_router(auth.router, prefix="/api/v2/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v2/users", tags=["Admin User Management"])
# app.include_router(history.router, prefix="/api/v2/history", tags=["User History"])
# app.include_router(chat_v3.router, prefix="/api/v3", tags=["Chat V3 (LangGraph Agent)"]) # [MỚI]

app.include_router(rbac.router, prefix="/api/v3/rbac", tags=["V3 Access Control (RBAC)"])
app.include_router(users_v3.router, prefix="/api/v3/users", tags=["V3 User Management"])
@app.get("/")
def root():
    return {"message": "API is running!"}
