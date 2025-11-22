from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Tải biến môi trường từ file .env.
# Đây là bước quan trọng để đọc GOOGLE_API_KEY
load_dotenv() 

# Định nghĩa lớp cấu hình sử dụng Pydantic BaseSettings
class Settings(BaseSettings):
    # Khóa API cho Google Gemini
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # Cấu hình Qdrant
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", 6333))
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "gym_food_collection")
    
    # Cấu hình dự án (từ file .env của bạn)
    PROJECT_NAME: str = "Gym Food RAG"
    API_V1_STR: str = "/api/v1"

# Khởi tạo instance của Settings
settings = Settings()

# Debugging: In ra host Qdrant để xác nhận nó đã được tải
print(f"INFO: Qdrant Host configured: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
if not settings.GOOGLE_API_KEY:
    # Nếu API key trống, in ra cảnh báo.
    print("WARNING: GOOGLE_API_KEY not found. Check your .env file or environment variables.")
else:
    # In ra một phần của API key để xác nhận nó đã được tải thành công.
    print(f"INFO: GOOGLE_API_KEY loaded successfully.")
    print(settings.GOOGLE_API_KEY[:5] + "..." + settings.GOOGLE_API_KEY[-5:])