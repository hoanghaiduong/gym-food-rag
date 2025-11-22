from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
import os

# Import Services
# Đảm bảo bạn đã có các file này trong thư mục app/services/
from app.services.embedding_factory import get_embedding_service
from app.services.llm_service_fully import get_llm_service
from app.services.cache_service import cache_service 

router = APIRouter()

# Config Qdrant
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME_V2 = os.getenv("COLLECTION_NAME", "gym_food_v2")

# Kết nối Qdrant (Dùng cho tìm kiếm dữ liệu chính)
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Khởi tạo Services
# embedder: Sẽ là BGE-M3 (Local) nếu .env USE_LOCAL_EMBEDDING=True
embedder = get_embedding_service()
# llm_service: Sẽ là Gemini (Cloud) nếu .env LLM_BACKEND=gemini
llm_service = get_llm_service()

class ChatRequest(BaseModel):
    question: str

@router.post("/chat")
async def chat_v2(request: ChatRequest):
    """
    API V2 Hybrid + Semantic Cache (Tối ưu tốc độ & Chi phí):
    1. Embedding câu hỏi (Local BGE-M3).
    2. Check Cache (Siêu nhanh) -> Nếu có trả về ngay.
    3. Nếu Miss -> Search Qdrant (Dữ liệu sạch V2).
    4. Generate Answer (Gemini Cloud - Nhanh).
    5. Save Cache (Để lần sau hỏi lại không tốn công nữa).
    """
    try:
        # 1. Embedding câu hỏi
        # is_query=True giúp model BGE/E5 thêm prefix "query:" để tìm kiếm chính xác hơn
        query_vector = embedder.embed_text(request.question, is_query=True)

        # --- BƯỚC KIỂM TRA CACHE ---
        cached_answer = cache_service.check_cache(query_vector)
        
        if cached_answer:
            # Lấy tên model embedding an toàn (để debug)
            emb_model_name = getattr(embedder, 'model_name', 'unknown-model')
            
            return {
                "answer": cached_answer,
                "backend_llm": "semantic_cache", # Đánh dấu là lấy từ Cache
                "backend_embedding": emb_model_name,
                "context_used": ["Dữ liệu được lấy từ bộ nhớ đệm (Cache) để phản hồi tức thì."]
            }
        # ---------------------------

        # 2. Tìm kiếm Vector trong Qdrant (Nếu Cache Miss)
        search_result = qdrant_client.search(
            collection_name=COLLECTION_NAME_V2,
            query_vector=query_vector,
            limit=5
        )

        # 3. Tạo Context
        if not search_result:
            # Nếu không tìm thấy, trả lời khéo léo
            return {
                "answer": "Xin lỗi, tôi chưa tìm thấy thông tin chính xác về món ăn này trong cơ sở dữ liệu dinh dưỡng của mình.",
                "backend_llm": llm_service.backend,
                "context_used": []
            }

        context_list = [hit.payload['content'] for hit in search_result]
        context = "\n".join(context_list)

        # 4. Tạo Prompt Chuyên gia
        prompt = f"""
        [INSTRUCTION]
        Bạn là trợ lý dinh dưỡng Gym người Việt Nam chuyên nghiệp.
        Nhiệm vụ: Trả lời câu hỏi của người dùng dựa trên CONTEXT dữ liệu bên dưới.
        
        YÊU CẦU BẮT BUỘC:
        1. CHỈ ĐƯỢC SỬ DỤNG TIẾNG VIỆT.
        2. Phân tích rõ Protein/Calo cho mục tiêu Bulking (xả cơ) hay Cutting (siết cơ).
        3. Trả lời ngắn gọn, súc tích nhưng đầy đủ thông tin, văn phong thân thiện.
        
        CONTEXT DỮ LIỆU:
        {context}
        
        CÂU HỎI: "{request.question}"
        
        TRẢ LỜI (BẰNG TIẾNG VIỆT):
        """
        
        # 5. Gửi cho LLM Service (Gemini Cloud sẽ xử lý rất nhanh)
        answer = llm_service.generate_answer(prompt)
        
        # --- BƯỚC LƯU CACHE ---
        # Lưu lại vector câu hỏi và câu trả lời vào Qdrant để dùng lại
        cache_service.save_to_cache(query_vector, request.question, answer)
        # ----------------------
        
        # Lấy tên model embedding
        emb_model_name = getattr(embedder, 'model_name', 'unknown-model')

        return {
            "answer": answer,
            "backend_llm": llm_service.backend,
            "backend_embedding": emb_model_name,
            "context_used": context_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))