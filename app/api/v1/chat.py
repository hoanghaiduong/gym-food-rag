from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services.llm_service import llm_service
from qdrant_client import QdrantClient
import traceback
import os

router = APIRouter()

# --- CẤU HÌNH RIÊNG CHO V1 ---
# Bắt buộc dùng Collection cũ để khớp với Gemini Embedding (768 chiều)
LEGACY_COLLECTION_NAME = "gym_food_collection"

# Kết nối Qdrant trực tiếp (Bỏ qua vector_db service để tránh đọc nhầm .env)
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

SYSTEM_PROMPT = """
Bạn là chuyên gia dinh dưỡng AI cho người tập Gym (Gym Nutritionist).
Nhiệm vụ của bạn là tư vấn thực đơn dựa trên dữ liệu dinh dưỡng chính xác được cung cấp.

QUY TẮC CỐT LÕI:
1. DỰA VÀO DỮ LIỆU (CONTEXT): Câu trả lời của bạn phải được xây dựng chủ yếu từ thông tin trong phần "CONTEXT INFORMATION" bên dưới.
2. TRUNG THỰC: Nếu không tìm thấy món ăn phù hợp trong Context, hãy nói "Tôi không tìm thấy dữ liệu về món ăn này trong hệ thống của Viện Dinh dưỡng". Đừng bịa ra số liệu.
3. PHÂN TÍCH MACRO: Khi gợi ý món ăn, hãy phân tích kỹ Protein, Carb, Fat và Calo xem nó phù hợp cho mục tiêu gì (Tăng cơ/Giảm mỡ).
4. NGÔN NGỮ: Thân thiện, chuyên nghiệp, dùng thuật ngữ Gym (Cutting, Bulking, Macro) khi cần thiết.
"""

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        print(f"--- [V1 Legacy] Nhận câu hỏi: {request.question} ---")
        
        # 1. Tạo vector bằng Gemini (Legacy method)
        # Hàm này trong LLMService mới vẫn gọi text-embedding-004 (768 chiều)
        print("1. Đang tạo vector Gemini (768 dims)...")
        query_vector = llm_service.get_embedding(request.question)
        
        if not query_vector:
            raise HTTPException(status_code=500, detail="Lỗi tạo vector embedding.")

        # 2. Tìm kiếm trong Collection Cũ (gym_food_collection)
        print(f"2. Đang tìm trong collection: {LEGACY_COLLECTION_NAME}...")
        search_results = qdrant_client.search(
            collection_name=LEGACY_COLLECTION_NAME,
            query_vector=query_vector,
            limit=5
        )
        print(f"   -> Tìm thấy {len(search_results)} kết quả.")
        
        # 3. Xây dựng Context
        sources = []
        context_text = ""
        
        if not search_results:
            context_text = "Không tìm thấy dữ liệu món ăn nào phù hợp."
        else:
            # Chuyển đổi format Qdrant sang dict để trả về API
            context_items = []
            for hit in search_results:
                payload = hit.payload
                context_items.append(f"Món: {payload.get('name')} - {payload.get('content')}")
                sources.append(payload) # Lưu lại source để trả về frontend
            
            context_text = "\n---\n".join(context_items)
        
        # 4. Gửi cho LLM
        # Dù V1 cũ dùng Gemini, nhưng nhờ LLMService mới,
        # nó sẽ tự động dùng Gemini hoặc Ollama tùy theo bạn set LLM_BACKEND trong .env
        # (Rất tiện: Dữ liệu cũ nhưng bộ não trả lời có thể là Llama 3 mới)
        print("3. Đang sinh câu trả lời...")
        answer = llm_service.generate_response(
            system_prompt=SYSTEM_PROMPT,
            user_question=request.question,
            context=context_text
        )
        
        return ChatResponse(
            answer=answer,
            sources=sources
        )

    except Exception as e:
        print("-------------------- START ERROR TRACEBACK --------------------")
        traceback.print_exc() 
        print("-------------------- END ERROR TRACEBACK --------------------")
        raise HTTPException(status_code=500, detail=str(e))