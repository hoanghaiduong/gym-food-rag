from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os
import uuid
# Import dependency bảo mật (nếu muốn bảo vệ API này)
from app.api.deps import verify_admin 
from app.services.embedding_bge_service import get_bge_service

router = APIRouter()

# Config
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
# Dùng tên collection mới hỗ trợ Hybrid
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "gym_food_hybrid_v1")

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
embedder = get_bge_service()

class NewFoodItem(BaseModel):
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    description: str = ""
    group: str = "User Added"

@router.post("/add-food")
async def add_food_knowledge(item: NewFoodItem, dependencies=[Depends(verify_admin)]): 
    """
    Admin API: Thêm món ăn mới vào trí tuệ của AI (Chuẩn Hybrid).
    """
    try:
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

        # --- [SỬA ĐỔI QUAN TRỌNG] TẠO HYBRID VECTOR ---
        # 1. Vector Ngữ nghĩa (Dense)
        dense_vector = embedder.embed_dense(content)
        
        # 2. Vector Từ khóa (Sparse) - Cần thiết cho Hybrid Search
        sparse_vector = embedder.embed_sparse(content)

        point_id = str(uuid.uuid4())
        
        # 3. Lưu vào Qdrant với cấu trúc Named Vectors
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    # Cấu trúc này bắt buộc phải khớp với lúc tạo collection
                    vector={
                        "dense": dense_vector,
                        "sparse": sparse_vector.as_object() 
                    },
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
            "message": f"Đã dạy AI học món '{item.name}' (Hybrid) thành công!",
            "id": point_id
        }

    except Exception as e:
        # In lỗi ra console server để dễ debug
        print(f"❌ Lỗi Admin Add Food: {e}")
        raise HTTPException(status_code=500, detail=str(e))