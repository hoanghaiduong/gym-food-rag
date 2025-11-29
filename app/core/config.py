from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Tải biến môi trường từ file .env
load_dotenv() 

class Settings(BaseSettings):
    # --- 1. APP CONFIG ---
    PROJECT_NAME: str = "Gym Food RAG"
    API_V1_STR: str = "/api/v1"
    ADMIN_SECRET_KEY: str = "gym-food-super-admin"

    # --- 2. SECURITY & AUTH (JWT) ---
    # Secret Key dùng để mã hóa Token (Cần khớp với file env nếu có, hoặc default)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "gym-food-super-secret-key-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30        # Access Token sống 30 phút
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7           # Refresh Token sống 7 ngày
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "") 
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    # --- 3. EMBEDDING & LLM ---
    GOOGLE_API_KEY: str = ""
    USE_LOCAL_EMBEDDING: bool = True
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    
    LLM_BACKEND: str = "gemini"  # 'gemini' hoặc 'ollama'
    GEMINI_MODEL: str = "gemini-2.5-flash"
    # Cấu hình Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # --- 4. VECTOR DB (QDRANT) ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    COLLECTION_NAME: str = "gym_food_hybrid_v1"

    # --- 5. POSTGRESQL DATABASE ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "admin"
    POSTGRES_DB: str = "gym_food_db"

    # --- 6. PGADMIN (Optional - Backend ít dùng nhưng khai báo cho đủ bộ) ---
    PGADMIN_EMAIL: str = "admin@gymfood.com"
    PGADMIN_PASSWORD: str = "admin"
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    # --- HELPER PROPERTY ---
    # Tự động tạo chuỗi kết nối DB chuẩn Psycopg 3 từ các biến rời rạc
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Cấu hình Pydantic để đọc file .env
    class Config:
        env_file = ".env"
        extra = "ignore"  # Bỏ qua các biến thừa trong .env nếu có

# Khởi tạo instance
settings = Settings()

# --- DEBUGGING INFO (In ra terminal khi khởi động) ---
print("-" * 50)
print(f"✅ Config Loaded: {settings.PROJECT_NAME}")
print(f"🔌 Database: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
print(f"🧠 LLM Backend: {settings.LLM_BACKEND.upper()}")
if settings.LLM_BACKEND == 'gemini':
    print(f"🔑 Google Key: {settings.GOOGLE_API_KEY[:5]}...{settings.GOOGLE_API_KEY[-5:] if settings.GOOGLE_API_KEY else 'MISSING'}")
    print(f"🦙 Gemini Model: {settings.GEMINI_MODEL}")
else:
    print(f"🦙 Ollama URL: {settings.OLLAMA_BASE_URL}")
print(f"🚀 Vector DB: {settings.QDRANT_HOST} (Collection: {settings.COLLECTION_NAME})")
print("-" * 50)