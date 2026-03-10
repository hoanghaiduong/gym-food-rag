import os
import sys
import time
import psutil
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

# Import dependency bảo mật từ file deps.py (Bạn nhớ tạo file này nhé)
from app.api.deps import verify_admin

router = APIRouter()

# --- CẤU HÌNH ---
# Lấy đường dẫn root để tìm file .env và log
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "app.log") # Giả sử log ghi vào đây

# --- MODEL DỮ LIỆU ---
class EnvUpdate(BaseModel):
    key: str
    value: str

# ==================================================================
# PHẦN 1: SYSTEM HEALTH & CONTROL (REST API)
# ==================================================================

from app.core.response import BaseResponse, success_response

# ... (Imports preserved, placed after existing)

# ==================================================================
# PHẦN 1: SYSTEM HEALTH & CONTROL (REST API)
# ==================================================================

@router.get("/health", response_model=BaseResponse) 
async def system_health():
    """Kiểm tra trạng thái server, RAM, CPU"""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    
    data = {
        "status": "online",
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "ram_usage_mb": round(mem_info.rss / 1024 / 1024, 2),
            "uptime_seconds": int(time.time() - process.create_time())
        },
        "backend": "FastAPI Hybrid RAG"
    }
    return success_response(data=data, message="Hệ thống hoạt động bình thường")

@router.get("/config", dependencies=[Depends(verify_admin)], response_model=BaseResponse)
async def get_config():
    """Đọc file .env (Che giấu thông tin nhạy cảm)"""
    config = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    # Che giấu API Key 
                    if "KEY" in key or "SECRET" in key or "PASSWORD" in key:
                        val = val[:5] + "..." + val[-3:] if len(val) > 10 else "***"
                    config[key] = val
    return success_response(data=config)

@router.post("/config/update", dependencies=[Depends(verify_admin)], response_model=BaseResponse)
async def update_env(data: EnvUpdate):
    """Cập nhật biến môi trường (Ghi file & update RAM)"""
    try:
        # 1. Ghi vào file .env vật lý
        set_key(ENV_PATH, data.key, data.value, quote_mode="never")
        
        # 2. Cập nhật RAM
        os.environ[data.key] = data.value
        
        return success_response(message=f"Đã cập nhật {data.key}. Hãy Restart để áp dụng triệt để.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/restart", dependencies=[Depends(verify_admin)], response_model=BaseResponse)
async def restart_server(background_tasks: BackgroundTasks):
    """Khởi động lại Server (Yêu cầu Docker restart: always)"""
    def kill_self():
        time.sleep(1) 
        print("💀 Admin yêu cầu Restart. Shutting down...")
        os._exit(1) 
    
    background_tasks.add_task(kill_self)
    return success_response(message="Server đang khởi động lại...")

# ==================================================================
# PHẦN 2: REAL-TIME LOGS (WEBSOCKET)
# ==================================================================

class LogStreamManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_log(self, message: str):
        # Gửi log cho tất cả client đang kết nối
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass 

log_manager = LogStreamManager()

# Task chạy ngầm đọc file log
async def watch_log_file():
    """Đọc file app.log và đẩy qua WebSocket"""
    if not os.path.exists(LOG_FILE_PATH):
        # Tạo file nếu chưa có
        with open(LOG_FILE_PATH, "w") as f: f.write("--- Log Stream Started ---\n")

    try:
        with open(LOG_FILE_PATH, "r") as f:
            # Di chuyển con trỏ tới cuối file để chỉ đọc log mới sinh ra
            f.seek(0, 2) 
            
            while True:
                line = f.readline()
                if line:
                    await log_manager.broadcast_log(line)
                else:
                    await asyncio.sleep(0.1) # Nghỉ để không tốn CPU
    except Exception as e:
        print(f"❌ Lỗi đọc file log: {e}")

@router.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket cho Frontend kết nối"""
    await log_manager.connect(websocket)
    try:
        while True:
            # Giữ kết nối sống
            await websocket.receive_text() 
    except WebSocketDisconnect:
        log_manager.disconnect(websocket)

