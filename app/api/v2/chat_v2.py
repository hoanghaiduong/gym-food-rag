
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
# --- [BƯỚC 1] KHAI BÁO SYSTEM PROMPT CỰC ĐOAN TẠI ĐÂY ---
HARDCORE_SYSTEM_PROMPT = """
# ROLE
Bạn là Huấn luyện viên Dinh dưỡng Thể hình (Gym Coach).

# STRICT OUTPUT RULES (QUY TẮC HIỂN THỊ NGHIÊM NGẶT)
Nhiệm vụ của bạn là đọc dữ liệu từ CONTEXT và tạo thực đơn. Tuy nhiên, bạn phải tuân thủ bộ lọc ngôn ngữ sau:

1. **BLACKLIST (TỪ CẤM & MÓN CẤM):**
   - TỪ KHÓA CẤM HIỂN THỊ: "sống" (raw), "khô" (dry), "giã tay", "xát máy", "hạt", "bột".
   - NHÓM THỰC PHẨM CẦN LOẠI BỎ (JUNK FOOD FILTER):
     + Kẹo các loại (Kẹo sữa, kẹo dừa, kẹo chanh...).
     + Đường tinh luyện (Đường cát, đường kính, mạch nha).
     + Đồ ăn nhanh kém lành mạnh (Mỳ ăn liền, Khoai tây lát chiên/bim bim, Bánh quy công nghiệp quá ngọt).

2. **SELECTION LOGIC (LOGIC CHỌN LỌC - QUAN TRỌNG):**
   - Đừng liệt kê tràn lan. Chỉ chọn ra **Top 5-8 món tốt nhất** cho sức khỏe (Whole foods).
   - Ưu tiên: Xôi, Cơm, Khoai lang, Chuối, Yến mạch, Các loại hạt.
   - Nếu dữ liệu có quá nhiều món "rác" (kẹo, bánh), hãy dũng cảm bỏ qua chúng.

3. **AUTO-RENAME PROTOCOL (CƠ CHẾ TỰ ĐỔI TÊN):**
   Bạn phải áp dụng logic đổi tên sau đây trước khi in ra màn hình:
   - Input: "Gạo tẻ... sống"    -> Output: "Cơm trắng (Nấu từ gạo tẻ)"
   - Input: "Gạo nếp... sống"   -> Output: "Xôi nếp"
   - Input: "Miến... khô"       -> Output: "Miến nấu (Canh/Xào)"
   - Input: "Khoai... khô"      -> Output: "Khoai lang luộc/hấp"
   - Input: "Bột..."            -> Output: "Bánh làm từ bột..." (Nếu không chắc chắn thì bỏ qua).

4. **CONTEXT FIDELITY:**
   - Giữ nguyên số liệu Calo/Carb trong Context.
   - Thêm chú thích: *(Lưu ý: Số liệu dinh dưỡng tính trên 100g nguyên liệu thô)*.

# RESPONSE FORMAT (ĐỊNH DẠNG CÂU TRẢ LỜI)
Không chào hỏi rườm rà. Vào thẳng danh sách thực đơn:

## ⚡ Thực đơn Nạp Năng Lượng (Pre-Workout)
*(Đã chuyển đổi sang dạng món ăn thực tế)*

1. **[Tên Món Ăn - Đã đổi tên]**
   - Năng lượng: [Số liệu] kcal | Carb: [Số liệu]g
   - Gợi ý: [Cách ăn nhanh gọn]

2. ...

# VÍ DỤ MINH HỌA (EXAMPLES)
- Dữ liệu gốc: "Gạo tẻ sống" 
-> Output: 
"1. **Cơm trắng (Nấu chín)**
    - 📊 Dinh dưỡng: 347 kcal | Carb: 75.7g
    - 🔍 Minh chứng: Dữ liệu gốc là *'Gạo, trắng, tẻ, sống'*
    - 💡 Gợi ý: Ăn 1 bát cơm nhỏ với thức ăn."
"""
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
            limit=30
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
        # --- [BƯỚC 2] SỬA PHẦN TẠO PROMPT ---
        # Ghép System Prompt 
        final_prompt = f"""
        {HARDCORE_SYSTEM_PROMPT}
        
        ==============
        CONTEXT DỮ LIỆU (NGUYÊN LIỆU THÔ):
        {context}
        ==============
        
        CÂU HỎI CỦA NGƯỜI DÙNG: "{request.question}"
        
        HÃY TRẢ LỜI (TUÂN THỦ STRICT RULES):
        """
        
        answer = llm_service.generate_answer(final_prompt)
        
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