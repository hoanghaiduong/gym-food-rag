from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os

# Import service cũ
from app.services.embedding_bge_service import get_bge_service

# Config
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "gym_food_hybrid_v1")

# Singleton Clients
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
embedder = get_bge_service()

@tool
def search_gym_food(query: str):
    """
    Công cụ tìm kiếm thông tin dinh dưỡng món ăn.
    Luôn sử dụng công cụ này khi người dùng hỏi về calo, protein, thực đơn, món ăn.
    """
    print(f"🕵️ [Agent V3] Đang tìm kiếm: {query}")
    
    try:
        # 1. Tạo Vector (Hybrid)
        dense = embedder.embed_dense(query)
        sparse = embedder.embed_sparse(query)
        
        # 2. Search Qdrant
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(query=dense, using="dense", limit=20),
                models.Prefetch(query=sparse.as_object(), using="sparse", limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=5 
        )
        
        if not results.points:
            return "Không tìm thấy dữ liệu món ăn này."
            
        # 3. Trả về text context cho LLM
        context = "\n".join([f"- {hit.payload['content']}" for hit in results.points])
        return context

    except Exception as e:
        return f"Lỗi khi tìm kiếm: {str(e)}"

# Xuất danh sách tool
agent_tools = [search_gym_food]