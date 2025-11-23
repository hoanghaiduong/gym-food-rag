import os
from fastapi import APIRouter, HTTPException, Depends
from dotenv import set_key
from sqlalchemy import create_engine, text
from qdrant_client import QdrantClient
import google.generativeai as genai

# Import models và auth
from app.api.deps import verify_admin
from app.models.schemas import DatabaseConfig, GeneralConfig, LLMConfig, NetworkConfig, VectorConfig
# Bạn copy các class BaseModel ở trên vào file schemas.py rồi import vào, 
# hoặc để chung file này cũng được cho gọn.

router = APIRouter()

# Đường dẫn file .env
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

def save_to_env(config_dict: dict):
    """Hàm helper để lưu vào .env"""
    try:
        for key, value in config_dict.items():
            # Chuyển key thành chữ hoa (ví dụ: api_base_url -> API_BASE_URL)
            env_key = key.upper()
            set_key(ENV_PATH, env_key, str(value), quote_mode="never")
            os.environ[env_key] = str(value) # Update RAM
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu file .env: {str(e)}")

# ============================================================
# STEP 1: BACKEND & NETWORK
# ============================================================
@router.post("/step1/save", dependencies=[Depends(verify_admin)])
async def save_network_config(config: NetworkConfig):
    # Bước này chủ yếu lưu URL để Frontend dùng sau này
    save_to_env(config.model_dump())
    return {"status": "success", "message": "Network configuration saved."}

# ============================================================
# STEP 2: DATABASE CONNECTION
# ============================================================
@router.post("/step2/test", dependencies=[Depends(verify_admin)])
async def test_database_connection(config: DatabaseConfig):
    """Thử kết nối tới PostgreSQL"""
    try:
        # Tạo connection string
        db_url = f"postgresql://{config.username}:{config.password}@{config.host}:{config.port}/{config.db_name}"
        engine = create_engine(db_url)
        
        # Thử kết nối
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            
        return {"status": "success", "message": "Connection established successfully!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database connection failed: {str(e)}")

@router.post("/step2/save", dependencies=[Depends(verify_admin)])
async def save_database_config(config: DatabaseConfig):
    # Lưu từng trường hoặc lưu full connection string
    db_url = f"postgresql://{config.username}:{config.password}@{config.host}:{config.port}/{config.db_name}"
    save_data = config.model_dump()
    save_data['DATABASE_URL'] = db_url # Tạo thêm biến gộp
    save_to_env(save_data)
    return {"status": "success", "message": "Database configuration saved."}

# ============================================================
# STEP 3: VECTOR SEARCH (RAG)
# ============================================================
@router.post("/step3/test", dependencies=[Depends(verify_admin)])
async def test_vector_db(config: VectorConfig):
    """Thử kết nối Qdrant và kiểm tra Collection"""
    try:
        # Kết nối
        client = QdrantClient(url=config.host, api_key=config.api_key, timeout=30)
        
        # Kiểm tra collection
        collections = client.get_collections().collections
        exists = any(c.name == config.collection_name for c in collections)
        
        if exists:
            return {"status": "success", "message": f"Connected! Collection '{config.collection_name}' found."}
        else:
            # Warning nhưng vẫn success connection
            return {"status": "warning", "message": f"Connected, but collection '{config.collection_name}' not found. It will be created later."}
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Qdrant connection failed: {str(e)}")

@router.post("/step3/save", dependencies=[Depends(verify_admin)])
async def save_vector_config(config: VectorConfig):
    # Mapping tên biến cho khớp với code cũ (QDRANT_HOST, PORT...)
    # Giả sử input host là "http://localhost:6333"
    try:
        url_parts = config.host.replace("http://", "").replace("https://", "").split(":")
        host = url_parts[0]
        port = url_parts[1] if len(url_parts) > 1 else "6333"
        
        save_data = {
            "QDRANT_HOST": host,
            "QDRANT_PORT": port,
            "COLLECTION_NAME": config.collection_name
        }
        save_to_env(save_data)
        return {"status": "success", "message": "Vector DB config saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# STEP 4: LLM CONFIGURATION
# ============================================================
@router.post("/step4/test", dependencies=[Depends(verify_admin)])
async def test_llm_connection(config: LLMConfig):
    """Gửi prompt 'Hello' tới Gemini để test key"""
    try:
        genai.configure(api_key=config.api_key)
        model = genai.GenerativeModel(config.model_name)
        response = model.generate_content("Hello, are you working?")
        
        if response.text:
            return {"status": "success", "message": "LLM Connected! Response received."}
        else:
            raise ValueError("Empty response from LLM")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"LLM Connection failed: {str(e)}")

@router.post("/step4/save", dependencies=[Depends(verify_admin)])
async def save_llm_config(config: LLMConfig):
    save_data = {
        "GOOGLE_API_KEY": config.api_key,
        "GEMINI_MODEL": config.model_name
    }
    save_to_env(save_data)
    return {"status": "success", "message": "LLM credentials saved."}

# ============================================================
# STEP 5: GENERAL SITE INFO
# ============================================================
@router.post("/step5/save", dependencies=[Depends(verify_admin)])
async def save_general_config(config: GeneralConfig):
    save_to_env(config.model_dump())
    return {"status": "success", "message": "Setup Completed!"}