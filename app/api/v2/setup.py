import os
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from dotenv import set_key
from pydantic import BaseModel
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Text, DateTime, func, inspect
from sqlalchemy.sql import text as sql_text
from qdrant_client import QdrantClient
import google.generativeai as genai

# Import models và auth
from app.api.deps import verify_admin
from app.api.v2.system import log_manager # Để bắn log ra màn hình
from app.db.migrations import run_db_migrations
from app.db.seeds import seed_initial_data
from app.models.schemas import (
    AdminSetupConfig, DatabaseConfig, GeneralConfig, 
    LLMConfig, NetworkConfig, VectorConfig
)

class MigrationRequest(BaseModel): # Model cục bộ cho migration
    force_reset: bool = False

router = APIRouter()

# Đường dẫn file .env
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

def save_to_env(config_dict: dict):
    """Hàm helper để lưu vào .env"""
    try:
        for key, value in config_dict.items():
            env_key = key.upper()
            set_key(ENV_PATH, env_key, str(value), quote_mode="never")
            os.environ[env_key] = str(value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu file .env: {str(e)}")

# ============================================================
# STEP 0: INIT ADMIN
# ============================================================
@router.post("/init-admin")
async def initialize_admin(config: AdminSetupConfig):
    current_key = os.getenv("ADMIN_SECRET_KEY", "gym-food-super-admin")
    if current_key != "gym-food-super-admin":
        raise HTTPException(status_code=400, detail="⛔ Admin đã được thiết lập. Không thể khởi tạo lại!")
    if len(config.admin_secret_key) < 8:
        raise HTTPException(status_code=400, detail="⚠️ Admin Key phải dài ít nhất 8 ký tự!")
    save_to_env({"ADMIN_SECRET_KEY": config.admin_secret_key})
    return {"status": "success", "message": "Đã tạo Admin Key thành công!"}

# ============================================================
# STEP 1: BACKEND & NETWORK
# ============================================================
@router.post("/step1/save", dependencies=[Depends(verify_admin)])
async def save_network_config(config: NetworkConfig):
    save_to_env(config.model_dump())
    return {"status": "success", "message": "Network configuration saved."}

# ============================================================
# STEP 2: DATABASE CONNECTION (PSYCOPG 3)
# ============================================================
@router.post("/step2/test", dependencies=[Depends(verify_admin)])
async def test_database(config: DatabaseConfig):
    try:
        url = f"postgresql+psycopg://{config.username}:{config.password}@{config.host}:{config.port}/{config.db_name}"
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "success", "message": "Kết nối DB thành công (Driver: Psycopg 3)!"}
    except Exception as e:
        err_msg = str(e)
        if "psycopg" in err_msg.lower():
            err_msg += " (Kiểm tra requirements.txt đã có 'psycopg[binary]' chưa?)"
        raise HTTPException(400, detail=f"Lỗi kết nối DB: {err_msg}")

@router.post("/step2/save", dependencies=[Depends(verify_admin)])
async def save_database_config(config: DatabaseConfig):
    db_url = f"postgresql+psycopg://{config.username}:{config.password}@{config.host}:{config.port}/{config.db_name}"
    save_data = config.model_dump()
    save_data['DATABASE_URL'] = db_url 
    save_to_env(save_data)
    return {"status": "success", "message": "Database configuration saved."}

# ============================================================
# STEP 2.5: DATABASE MIGRATION (SMART CHECK)
# ============================================================
@router.get("/step4/db-status", dependencies=[Depends(verify_admin)])
async def check_db_status():
    db_url = os.getenv("DATABASE_URL")
    if not db_url: raise HTTPException(400, "Chưa cấu hình Database.")
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return {
            "status": "dirty" if len(tables) > 0 else "clean",
            "tables": tables,
            "message": f"Found {len(tables)} tables." if tables else "Database empty."
        }
    except Exception as e:
        raise HTTPException(500, f"Error: {e}")

@router.post("/step4/db-migrate", dependencies=[Depends(verify_admin)])
async def execute_migration_endpoint(request: MigrationRequest):
    db_url = os.getenv("DATABASE_URL")
    if not db_url: raise HTTPException(400, "Missing DATABASE_URL.")
    
    # Hàm log bắn ra WebSocket
    async def ws_log(msg): 
        await log_manager.broadcast_log(msg)

    try:
        engine = create_engine(db_url)
        
        # 1. Chạy Migration
        await run_db_migrations(engine, request.force_reset, ws_log)
        
        # 2. Chạy Seeding
        await seed_initial_data(engine, ws_log)

        await ws_log("[DONE] System initialization complete!")
        return {"status": "success", "message": "Database initialized."}
        
    except Exception as e:
        await ws_log(f"[ERROR] {str(e)}")
        raise HTTPException(500, str(e))
# ============================================================
# STEP 3: VECTOR SEARCH (RAG)
# ============================================================
@router.post("/step3/test", dependencies=[Depends(verify_admin)])
async def test_vector_db(config: VectorConfig):
    try:
        client = QdrantClient(url=config.host, api_key=config.api_key, timeout=5)
        colls = client.get_collections().collections
        exists = any(c.name == config.collection_name for c in colls)
        if exists: return {"status": "success", "message": f"Connected! Collection '{config.collection_name}' found."}
        return {"status": "warning", "message": "Connected, but collection not found."}
    except Exception as e:
        raise HTTPException(400, f"Qdrant connection failed: {str(e)}")

@router.post("/step3/save", dependencies=[Depends(verify_admin)])
async def save_vector_config(config: VectorConfig):
    try:
        url_parts = config.host.replace("http://", "").replace("https://", "").split(":")
        host = url_parts[0]
        port = url_parts[1] if len(url_parts) > 1 else "6333"
        save_to_env({
            "QDRANT_HOST": host, "QDRANT_PORT": port, "COLLECTION_NAME": config.collection_name
        })
        return {"status": "success", "message": "Vector DB config saved."}
    except Exception as e:
        raise HTTPException(500, str(e))

# ============================================================
# STEP 4: LLM CONFIGURATION
# ============================================================
@router.post("/step4/test", dependencies=[Depends(verify_admin)])
async def test_llm_connection(config: LLMConfig):
    try:
        genai.configure(api_key=config.api_key)
        model = genai.GenerativeModel(config.model_name)
        response = model.generate_content("Hello")
        if response.text: return {"status": "success", "message": "LLM Connected!"}
        raise ValueError("Empty response")
    except Exception as e:
        raise HTTPException(400, f"LLM Failed: {str(e)}")

@router.post("/step4/save", dependencies=[Depends(verify_admin)])
async def save_llm_config(config: LLMConfig):
    save_to_env({"GOOGLE_API_KEY": config.api_key, "GEMINI_MODEL": config.model_name})
    return {"status": "success", "message": "LLM credentials saved."}

# ============================================================
# STEP 5: GENERAL SITE INFO
# ============================================================
@router.post("/step5/save", dependencies=[Depends(verify_admin)])
async def save_general_config(config: GeneralConfig):
    save_to_env(config.model_dump())
    return {"status": "success", "message": "Setup Completed!"}