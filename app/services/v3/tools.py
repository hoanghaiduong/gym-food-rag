import os
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Import service Embedding cũ (để tái sử dụng logic embed)
from app.services.embedding_bge_service import get_bge_service

# --- CONFIG ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "gym_food_hybrid_v1")

# Singleton Clients
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
embedder = get_bge_service()

@tool
def search_gym_food(query: str):
    """
    CÔNG CỤ TRA CỨU MÓN ĂN.
    Sử dụng tool này khi user hỏi về: Calo, Protein, Thành phần dinh dưỡng, Gợi ý thực đơn, So sánh món ăn.
    
    Args:
        query (str): Từ khóa món ăn cần tìm (Ví dụ: "phở bò", "ức gà", "thực đơn giảm cân").
    """
    print(f"🕵️ [Agent Tool] Đang tìm kiếm Hybrid cho: '{query}'")
    
    try:
        # 1. Tạo Vector 2 chiều (Hybrid Search)
        # Đây là nơi logic Sparse + Dense thực sự diễn ra để đảm bảo độ chính xác
        dense_vector = embedder.embed_dense(query)
        sparse_vector = embedder.embed_sparse(query)
        
        # 2. Query Qdrant
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(query=dense_vector, using="dense", limit=20),
                models.Prefetch(query=sparse_vector.as_object(), using="sparse", limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF), # Reciprocal Rank Fusion
            limit=5 # Lấy 5 kết quả tốt nhất
        )
        
        # 3. Xử lý kết quả trả về
        if not search_result.points:
            return "SYSTEM_MSG: Không tìm thấy món ăn nào khớp trong cơ sở dữ liệu."
            
        # Format dữ liệu thành văn bản để LLM đọc
        context_parts = []
        for hit in search_result.points:
            content = hit.payload.get('content', 'N/A')
            context_parts.append(f"- {content}")
            
        return "\n".join(context_parts)

    except Exception as e:
        return f"SYSTEM_ERROR: Lỗi truy vấn Database: {str(e)}"

# Export danh sách tools
agent_tools = [search_gym_food]