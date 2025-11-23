# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from qdrant_client import QdrantClient
# import os

# # Import Services
# # Đảm bảo bạn đã có các file này trong thư mục app/services/
# from app.services.embedding_factory import get_embedding_service
# from app.services.llm_service_fully import get_llm_service
# from app.services.cache_service import cache_service 

# router = APIRouter()

# # Config Qdrant
# QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
# QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
# COLLECTION_NAME_V2 = os.getenv("COLLECTION_NAME", "gym_food_v2")

# # Kết nối Qdrant (Dùng cho tìm kiếm dữ liệu chính)
# qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# # Khởi tạo Services
# # embedder: Sẽ là BGE-M3 (Local) nếu .env USE_LOCAL_EMBEDDING=True
# embedder = get_embedding_service()
# # llm_service: Sẽ là Gemini (Cloud) nếu .env LLM_BACKEND=gemini
# llm_service = get_llm_service()

# class ChatRequest(BaseModel):
#     question: str

# @router.post("/chat")
# async def chat_v2(request: ChatRequest):
#     """
#     API V2 Hybrid + Semantic Cache (Tối ưu tốc độ & Chi phí):
#     1. Embedding câu hỏi (Local BGE-M3).
#     2. Check Cache (Siêu nhanh) -> Nếu có trả về ngay.
#     3. Nếu Miss -> Search Qdrant (Dữ liệu sạch V2).
#     4. Generate Answer (Gemini Cloud - Nhanh).
#     5. Save Cache (Để lần sau hỏi lại không tốn công nữa).
#     """
#     try:
#         # 1. Embedding câu hỏi
#         # is_query=True giúp model BGE/E5 thêm prefix "query:" để tìm kiếm chính xác hơn
#         query_vector = embedder.embed_text(request.question, is_query=True)

#         # --- BƯỚC KIỂM TRA CACHE ---
#         cached_answer = cache_service.check_cache(query_vector)
        
#         if cached_answer:
#             # Lấy tên model embedding an toàn (để debug)
#             emb_model_name = getattr(embedder, 'model_name', 'unknown-model')
            
#             return {
#                 "answer": cached_answer,
#                 "backend_llm": "semantic_cache", # Đánh dấu là lấy từ Cache
#                 "backend_embedding": emb_model_name,
#                 "context_used": ["Dữ liệu được lấy từ bộ nhớ đệm (Cache) để phản hồi tức thì."]
#             }
#         # ---------------------------

#         # 2. Tìm kiếm Vector trong Qdrant (Nếu Cache Miss)
#         search_result = qdrant_client.search(
#             collection_name=COLLECTION_NAME_V2,
#             query_vector=query_vector,
#             limit=5
#         )

#         # 3. Tạo Context
#         if not search_result:
#             # Nếu không tìm thấy, trả lời khéo léo
#             return {
#                 "answer": "Xin lỗi, tôi chưa tìm thấy thông tin chính xác về món ăn này trong cơ sở dữ liệu dinh dưỡng của mình.",
#                 "backend_llm": llm_service.backend,
#                 "context_used": []
#             }

#         context_list = [hit.payload['content'] for hit in search_result]
#         context = "\n".join(context_list)

#         # 4. Tạo Prompt Chuyên gia
#         prompt = f"""
#         [INSTRUCTION]
#         Bạn là trợ lý dinh dưỡng Gym người Việt Nam chuyên nghiệp.
#         Nhiệm vụ: Trả lời câu hỏi của người dùng dựa trên CONTEXT dữ liệu bên dưới.
        
#         YÊU CẦU BẮT BUỘC:
#         1. CHỈ ĐƯỢC SỬ DỤNG TIẾNG VIỆT.
#         2. Phân tích rõ Protein/Calo cho mục tiêu Bulking (xả cơ) hay Cutting (siết cơ).
#         3. Trả lời ngắn gọn, súc tích nhưng đầy đủ thông tin, văn phong thân thiện.
        
#         CONTEXT DỮ LIỆU:
#         {context}
        
#         CÂU HỎI: "{request.question}"
        
#         TRẢ LỜI (BẰNG TIẾNG VIỆT):
#         """
        
#         # 5. Gửi cho LLM Service (Gemini Cloud sẽ xử lý rất nhanh)
#         answer = llm_service.generate_answer(prompt)
        
#         # --- BƯỚC LƯU CACHE ---
#         # Lưu lại vector câu hỏi và câu trả lời vào Qdrant để dùng lại
#         cache_service.save_to_cache(query_vector, request.question, answer)
#         # ----------------------
        
#         # Lấy tên model embedding
#         emb_model_name = getattr(embedder, 'model_name', 'unknown-model')

#         return {
#             "answer": answer,
#             "backend_llm": llm_service.backend,
#             "backend_embedding": emb_model_name,
#             "context_used": context_list
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models # [QUAN TRỌNG] Import models để dùng Prefetch
import os

# Import Services
from app.services.embedding_bge_service import get_bge_service # Dùng service mới đã sửa
from app.services.llm_service_fully import get_llm_service
from app.services.cache_service import cache_service 

router = APIRouter()

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
# Đảm bảo tên collection khớp với bên admin.py
COLLECTION_NAME_V2 = os.getenv("COLLECTION_NAME", "gym_food_hybrid_v1") 

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
embedder = get_bge_service()
llm_service = get_llm_service()

class ChatRequest(BaseModel):
    question: str

@router.post("/chat")
async def chat_v2(request: ChatRequest):
    """
    API V2 Hybrid Search (Semantic + Keyword) + Cache
    """
    try:
        # 1. Tạo Vector cho câu hỏi (Cả 2 loại)
        query_dense = embedder.embed_dense(request.question)
        query_sparse = embedder.embed_sparse(request.question)

        # --- BƯỚC KIỂM TRA CACHE ---
        # Với cache, ta tạm thời chỉ dùng Dense Vector để so sánh độ tương đồng nhanh
        cached_answer = cache_service.check_cache(query_dense)
        
        if cached_answer:
            emb_model_name = getattr(embedder, 'model_name', 'unknown-model')
            return {
                "answer": cached_answer,
                "backend_llm": "semantic_cache",
                "backend_embedding": emb_model_name,
                "context_used": ["Dữ liệu lấy từ Cache."]
            }
        # ---------------------------

        # 2. [MỚI] HYBRID SEARCH (Tìm kiếm lai)
        # Thay vì .search(), ta dùng .query_points() mạnh hơn
        search_result = qdrant_client.query_points(
            collection_name=COLLECTION_NAME_V2,
            prefetch=[
                # Truy vấn 1: Tìm bằng Ngữ nghĩa (Dense) - Hiểu ý định
                models.Prefetch(
                    query=query_dense,
                    using="dense",
                    limit=100, 
                ),
                # Truy vấn 2: Tìm bằng Từ khóa (Sparse) - Bắt chính xác tên món
                models.Prefetch(
                    query=query_sparse.as_object(),
                    using="sparse",
                    limit=100,
                ),
            ],
            # Trộn kết quả bằng thuật toán RRF (Reciprocal Rank Fusion)
            # RRF giúp cân bằng: món nào vừa đúng ý nghĩa, vừa đúng từ khóa sẽ lên đầu
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=50
        )

        # 3. Xử lý kết quả
        if not search_result.points:
            return {
                "answer": "Xin lỗi, tôi chưa tìm thấy thông tin về món này trong dữ liệu.",
                "backend_llm": llm_service.backend,
                "context_used": []
            }

        context_list = [hit.payload['content'] for hit in search_result.points]
        context = "\n".join(context_list)

        # 4. Tạo Prompt & Gọi Gemini (Giữ nguyên logic tốt của bạn)
        prompt = f"""
        [INSTRUCTION]
        Bạn là chuyên gia dinh dưỡng Gym. Trả lời câu hỏi dựa trên CONTEXT bên dưới.
        
        CONTEXT DỮ LIỆU:
        {context}
        
        CÂU HỎI: "{request.question}"
        
        TRẢ LỜI (TIẾNG VIỆT):
        """
        
        answer = llm_service.generate_answer(prompt)
        
        # 5. Lưu Cache
        cache_service.save_to_cache(query_dense, request.question, answer)
        
        emb_model_name = getattr(embedder, 'model_name', 'unknown-model')

        return {
            "answer": answer,
            "backend_llm": llm_service.backend,
            "backend_embedding": emb_model_name,
            "context_used": context_list
        }

    except Exception as e:
        # In lỗi ra console để debug dễ hơn
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))