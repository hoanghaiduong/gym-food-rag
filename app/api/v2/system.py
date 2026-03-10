import asyncio
import os
import time

import psutil
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from dotenv import set_key

from app.api.deps import verify_admin
from app.core.paths import LOG_FILE_PATH, PROJECT_ROOT
from app.core.response import BaseResponse, success_response


router = APIRouter()
ENV_PATH = PROJECT_ROOT / ".env"


class EnvUpdate(BaseModel):
    key: str
    value: str


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
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


log_manager = LogStreamManager()


@router.get("/health", response_model=BaseResponse[dict])
async def system_health():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    data = {
        "status": "online",
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "ram_usage_mb": round(mem_info.rss / 1024 / 1024, 2),
            "uptime_seconds": int(time.time() - process.create_time()),
        },
        "backend": "FastAPI Hybrid RAG",
    }
    return success_response(data=data, message="Hệ thống hoạt động bình thường")


@router.get("/config", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def get_config():
    config: dict[str, str] = {}
    if ENV_PATH.exists():
        with ENV_PATH.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if "=" not in line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                if "KEY" in key or "SECRET" in key or "PASSWORD" in key:
                    value = value[:5] + "..." + value[-3:] if len(value) > 10 else "***"
                config[key] = value
    return success_response(data=config, message="Đọc cấu hình thành công")


@router.post("/config/update", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def update_env(data: EnvUpdate):
    try:
        set_key(str(ENV_PATH), data.key, data.value, quote_mode="never")
        os.environ[data.key] = data.value
        return success_response(message=f"Đã cập nhật {data.key}. Hãy restart để áp dụng đầy đủ.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/restart", dependencies=[Depends(verify_admin)], response_model=BaseResponse[dict])
async def restart_server(background_tasks: BackgroundTasks):
    def kill_self():
        time.sleep(1)
        os._exit(1)

    background_tasks.add_task(kill_self)
    return success_response(message="Server đang khởi động lại...")


async def watch_log_file():
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE_PATH.exists():
        LOG_FILE_PATH.write_text("--- Log Stream Started ---\n", encoding="utf-8")

    try:
        with LOG_FILE_PATH.open("r", encoding="utf-8") as file:
            file.seek(0, 2)
            while True:
                line = file.readline()
                if line:
                    await log_manager.broadcast_log(line)
                else:
                    await asyncio.sleep(0.1)
    except Exception as exc:
        print(f"Lỗi đọc file log: {exc}")


@router.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await log_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        log_manager.disconnect(websocket)
