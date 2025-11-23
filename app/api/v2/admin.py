from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os
import uuid
from app.services.embedding_factory import get_embedding_service
# Lấy đúng service BGE
from app.services.embedding_bge_service import get_bge_service 

router = APIRouter()

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "gym_food_hybrid_v1") # Đổi tên mới

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
embedder = get_bge_service() # Dùng trực tiếp class đã sửa ở Bước 2

class NewFoodItem(BaseModel):
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    description: str = ""
    group: str = "User Added"

@router.post("/init-collection")
async def init_hybrid_collection():
    """API chạy 1 lần để tạo bảng dữ liệu Hybrid"""
    if qdrant_client.collection_exists(COLLECTION_NAME):
        return {"message": "Collection đã tồn tại."}
    
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False))
        }
    )
    return {"message": f"Đã tạo Hybrid Collection: {COLLECTION_NAME}"}

@router.post("/add-food")
async def add_food_knowledge(item: NewFoodItem):
    try:
        gym_advice = ""
        if item.protein > 20: gym_advice = "Giàu protein, tốt cho tăng cơ."
        
        content = (
            f"Món ăn: {item.name}. "
            f"Dinh dưỡng: {item.calories} kcal, Protein {item.protein}g, "
            f"Fat {item.fat}g, Carb {item.carbs}g. "
            f"{item.description}. {gym_advice} "
            f"Nhóm: {item.group}."
        )

        # 1. Tạo Dense Vector
        dense_vector = embedder.embed_dense(content)
        
        # 2. Tạo Sparse Vector (MỚI)
        sparse_vector = embedder.embed_sparse(content)

        point_id = str(uuid.uuid4())
        
        # 3. Upsert kiểu Hybrid (Named Vectors)
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vector,
                        "sparse": sparse_vector.as_object() # Convert object splade
                    },
                    payload={
                        "name": item.name,
                        "content": content,
                        "protein_g": item.protein,
                        "kcal": item.calories
                    }
                )
            ]
        )

        return {"status": "success", "id": point_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))