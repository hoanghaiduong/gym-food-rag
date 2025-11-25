import os
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from dotenv import set_key

from pydantic import BaseModel
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Text, DateTime, func, inspect
from sqlalchemy.sql import text as sql_text
from sqlalchemy.dialects.postgresql import insert # Import tính năng Upsert
from qdrant_client import QdrantClient
import google.generativeai as genai

# Import models và auth
from app.api.deps import verify_admin
from app.api.v2 import users
from app.api.v2.system import log_manager 
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.migrations import run_db_migrations
from app.db.seeds import seed_initial_data
from app.db.schemas import system_settings,users # Import bảng settings để lưu Step 5
from app.models.schemas import (
    AdminSetupConfig, DatabaseConfig, FirstAdminRequest, GeneralConfig, 
    LLMConfig, NetworkConfig, VectorConfig
)

class MigrationRequest(BaseModel):
    force_reset: bool = False

router = APIRouter()
DEFAULT_ADMIN_KEY = "gym-food-super-admin"
# Đường dẫn file .env
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
def save_to_env(config_dict: dict):
    """Hàm helper để lưu vào .env"""
    try:
        for key, value in config_dict.items():
            env_key = key.upper()
            
            # [FIX] Đổi thành "always" để luôn bọc dấu ngoặc kép "..."
            # Giúp xử lý tốt chuỗi có dấu cách hoặc ký tự đặc biệt
            set_key(ENV_PATH, env_key, str(value), quote_mode="always")
            
            os.environ[env_key] = str(value) # Update RAM
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu file .env: {str(e)}")
@router.get("/status")
async def get_system_status():
    """
    Kiểm tra trạng thái hệ thống.
    QUAN TRỌNG: Phải đọc trực tiếp từ os.getenv hoặc file .env để lấy giá trị mới nhất,
    không được dùng object 'settings' đã cached từ lúc khởi động.
    """
    
    # 1. Đọc trực tiếp biến môi trường mới nhất
    # (Vì code setup vừa ghi vào os.environ ở các bước trước)
    current_key = os.getenv("ADMIN_SECRET_KEY", "gym-food-super-admin")
    default_key = "gym-food-super-admin"

    # 2. Logic kiểm tra Admin Key (Step 0)
    if current_key == default_key:
        return {
            "status": "pending", 
            "requires_auth": False, 
            "step": 0,
            "message": "Hệ thống chưa bảo mật (Admin Key mặc định)."
        }
    api_base = os.getenv("API_BASE_URL")
    if not api_base:
        return {
            "status": "pending", 
            "requires_auth": True, 
            "step": 1, # <--- Trả về Step 1
            "message": "Chưa cấu hình Network (API Base URL)."
        }
    # 3. Logic kiểm tra Database (Step 2 & 4)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
         return {
             "status": "pending", 
             "requires_auth": True, # Đã có key nhưng thiếu DB
             "step": 2,
             "message": "Chưa cấu hình Database."
         }

    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # 1. Check Bảng
        if 'users' not in inspector.get_table_names():
            return {
                "status": "pending", "requires_auth": True, "step": 4,
                "message": "Chưa khởi tạo cấu trúc bảng (Cần Migrate)."
            }
        
        # 2. [MỚI] Check Dữ Liệu Admin
        with engine.connect() as conn:
             admin_count = conn.execute(
                 sql_text("SELECT count(*) FROM users WHERE role='admin'")
             ).scalar()
             
             if admin_count == 0:
                 return {
                     "status": "pending", "requires_auth": True, 
                     "step": 4.5, # Bước mới: Tạo Admin
                     "message": "Chưa có tài khoản Admin (Cần tạo)."
                 }

    except Exception as e:
        return {"status": "pending", "requires_auth": True, "step": 2, "message": str(e)}

    # Nếu đã có Admin Key + Có Bảng + Có Admin User -> Completed
    return {
        "status": "completed", 
        "requires_auth": True, 
        "message": "Hệ thống đã sẵn sàng."
    }
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
# STEP 1: BACKEND & NETWORK (Lưu .env)
# ============================================================
@router.post("/step1/save", dependencies=[Depends(verify_admin)])
async def save_network_config(config: NetworkConfig):
    save_to_env(config.model_dump())
    return {"status": "success", "message": "Network configuration saved."}

# ============================================================
# STEP 2: DATABASE CONNECTION (Lưu .env)
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
# STEP 2.5: DATABASE MIGRATION
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
    
    async def ws_log(msg): 
        await log_manager.broadcast_log(msg)

    try:
        engine = create_engine(db_url)
        await run_db_migrations(engine, request.force_reset, ws_log)
        await seed_initial_data(engine, ws_log)
        await ws_log("[DONE] System initialization complete!")
        return {"status": "success", "message": "Database initialized."}
    except Exception as e:
        await ws_log(f"[ERROR] {str(e)}")
        raise HTTPException(500, str(e))
# ============================================================
# STEP 2.6: CREATE FIRST ADMIN (Manual via UI)
# ============================================================
@router.post("/create-first-admin", dependencies=[Depends(verify_admin)])
async def create_first_admin(data: FirstAdminRequest):
    """
    Tạo tài khoản Admin đầu tiên từ giao diện Setup.
    Chỉ cho phép tạo nếu chưa có Admin nào trong hệ thống.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(400, "Chưa cấu hình Database.")

    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            # 1. Kiểm tra an toàn: Nếu đã có admin rồi thì chặn lại (tránh ghi đè ác ý)
            existing_admin = conn.execute(
                sql_text("SELECT count(*) FROM users WHERE role='admin'")
            ).scalar()
            
            if existing_admin > 0:
                return {
                    "status": "warning", 
                    "message": "Tài khoản Admin đã tồn tại. Bỏ qua bước này."
                }

            raw_password = data.password
            if len(raw_password.encode('utf-8')) > 72:
                raw_password = raw_password[:72]
            # 2. Hash mật khẩu
            hashed_pw = get_password_hash(raw_password)

            # 3. Insert vào DB
            conn.execute(users.insert().values(
                username=data.username,
                email=data.email,
                password_hash=hashed_pw,
                full_name=data.full_name,
                role='admin',     # Quyền cao nhất
                is_active=True
            ))
            
        return {
            "status": "success", 
            "message": f"Tài khoản Admin '{data.username}' đã được tạo thành công!"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo Admin: {str(e)}")
# ============================================================
# STEP 3: VECTOR SEARCH (Lưu .env)
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
# STEP 4: LLM CONFIGURATION (Lưu .env)
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
# STEP 5: GENERAL SITE INFO (Lưu CẢ 2: Database & .Env)
# ============================================================
@router.post("/step5/save", dependencies=[Depends(verify_admin)])
async def save_general_config(config: GeneralConfig):
    """
    Lưu cấu hình chung vào cả .env và Database để dự phòng.
    """
    # --- 1. LƯU VÀO FILE .ENV ---
    try:
        save_to_env(config.model_dump())
        print("✅ Đã lưu cấu hình vào .env")
    except Exception as e:
        print(f"⚠️ Cảnh báo: Không lưu được vào .env: {e}")

    # --- 2. LƯU VÀO DATABASE ---
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Nếu chưa có DB thì thôi, coi như xong (vì đã lưu .env rồi)
        return {"status": "warning", "message": "Đã lưu vào .env, nhưng chưa kết nối DB để lưu bảng settings."}
    
    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            settings_to_save = config.model_dump()
            for key, value in settings_to_save.items():
                # Upsert vào bảng system_settings
                stmt = insert(system_settings).values(key=key, value=str(value))
                do_update_stmt = stmt.on_conflict_do_update(
                    index_elements=['key'],
                    set_=dict(value=str(value))
                )
                conn.execute(do_update_stmt)
        print("✅ Đã lưu cấu hình vào Database")
                
    except Exception as e:
        # Nếu lỗi DB thì báo lỗi cho Frontend biết
        raise HTTPException(status_code=500, detail=f"Lỗi lưu DB: {str(e)}")

    return {"status": "success", "message": "Cấu hình đã được lưu đồng bộ (File + Database)!"}