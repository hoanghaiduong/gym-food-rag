from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os
import uuid

from app.services.embedding_factory import get_embedding_service

router = APIRouter()

# Config
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "gym_food_v2")

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
embedder = get_embedding_service()

class NewFoodItem(BaseModel):
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    description: str = ""
    group: str = "User Added"

@router.post("/add-food")
async def add_food_knowledge(item: NewFoodItem):
    """
    Admin API: Thêm món ăn mới vào trí tuệ của AI.
    """
    try:
        # 1. Tạo nội dung ngữ cảnh (Context)
        # Tự động tạo câu mô tả chuẩn để AI dễ hiểu
        gym_advice = ""
        if item.protein > 20: gym_advice = "Giàu protein, tốt cho tăng cơ."
        if item.calories > 500: gym_advice += " Năng lượng cao, cẩn thận khi cutting."
        
        content = (
            f"Món ăn: {item.name}. "
            f"Dinh dưỡng: {item.calories} kcal, Protein {item.protein}g, "
            f"Fat {item.fat}g, Carb {item.carbs}g. "
            f"{item.description}. {gym_advice} "
            f"Nhóm: {item.group}. Nguồn: Admin cập nhật."
        )

        # 2. Vector hóa (Dùng BGE-M3 hoặc Gemini tùy cấu hình .env)
        vector = embedder.embed_document(content)

        # 3. Lưu vào Qdrant
        # Dùng UUID để tạo ID duy nhất cho món mới
        point_id = str(uuid.uuid4())
        
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "name": item.name,
                        "content": content,
                        "protein_g": item.protein,
                        "kcal": item.calories,
                        "is_admin_added": True
                    }
                )
            ]
        )

        return {
            "status": "success", 
            "message": f"Đã dạy AI học món '{item.name}' thành công!",
            "id": point_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))