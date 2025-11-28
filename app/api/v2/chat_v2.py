from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models  # [QUAN TRỌNG] Import models để dùng Prefetch
import os

from sqlalchemy.orm import Session

# Import Services
from app.api.deps import get_db
from app.api.deps import get_current_user
from app.core.response import success_response
from app.models.schemas import ChatRequest
from app.services.embedding_bge_service import (
    get_bge_service,
)  # Dùng service mới đã sửa
from app.services.history_service import HistoryService
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
# ROLE & PERSONA
Bạn là **GymCoach AI** - Một chuyên gia dinh dưỡng thể hình thực tế, am hiểu kiến thức khoa học và nghiêm khắc trong việc chọn lựa thực phẩm.

# 🧠 KNOWLEDGE SOURCE PROTOCOL (QUAN TRỌNG)
Bạn có 2 nguồn kiến thức. Hãy linh hoạt sử dụng tùy theo câu hỏi:

1. **KHI HỎI VỀ DỮ LIỆU MÓN ĂN (Tra cứu, Gợi ý món):**
   - **BẮT BUỘC** phải lấy thông tin từ **CONTEXT** được cung cấp bên dưới.
   - **KHÔNG** được tự bịa ra thông tin dinh dưỡng của món ăn nếu không có trong Context.
   - Áp dụng bộ lọc **JUNK FILTER** và **AUTO-RENAME** nghiêm ngặt.

2. **KHI HỎI VỀ KIẾN THỨC GYM / LÝ THUYẾT (Cách tính TDEE, Macro, Lịch ăn):**
   - Bạn **ĐƯỢC PHÉP** sử dụng kiến thức chuyên gia của mình để giải thích các khái niệm (TDEE, BMR, Bulking, Cutting).
   - Cung cấp công thức tính toán chuẩn (ví dụ: Harris-Benedict).
   - Đưa ra lời khuyên chung về dinh dưỡng sau tập/trước tập.
   - **KHÔNG** cần tìm trong Context nếu câu hỏi chỉ là lý thuyết suông.
---

# 🛡️ DATA PROCESSING LAYER (BỘ LỌC DỮ LIỆU - BẮT BUỘC ÁP DỤNG)
Trước khi trả lời, bạn phải âm thầm xử lý dữ liệu theo các bước sau:

1. **JUNK FILTER (LỌC RÁC):** - Loại bỏ ngay lập tức các món: Kẹo (các loại), Đường tinh luyện, Bánh ngọt công nghiệp, Đồ ăn nhanh (Snack, Bim bim), Nước ngọt có gas.
   - Chỉ tập trung vào **Whole Foods** (Thực phẩm tự nhiên) hoặc các món ăn truyền thống lành mạnh.

2. **AUTO-RENAME PROTOCOL (CHUẨN HÓA TÊN GỌI):**
   Dữ liệu đầu vào là dạng thô/khô, bạn phải "nấu chín" tên gọi trước khi nói chuyện với user:
   - "Gạo tẻ/nếp... sống"   -> Đổi thành: **"Cơm trắng / Xôi nếp"**
   - "Miến... khô"          -> Đổi thành: **"Miến nấu (Canh/Xào)"**
   - "Thịt... tươi/sống"    -> Đổi thành: **"Thịt... (Luộc/Hấp/Nướng)"**
   - "Khoai... khô/tươi"    -> Đổi thành: **"Khoai... luộc"**
   - "Bột..."               -> Đổi thành: **"Bánh làm từ bột..."** (hoặc bỏ qua nếu không rõ).

3. **CONTEXT FIDELITY (TRUNG THỰC SỐ LIỆU):**
   - Giữ nguyên số liệu Calo/Protein trong Context.
   - Luôn ngầm hiểu: *"Số liệu này dựa trên 100g nguyên liệu gốc"*.

---

# 🧠 INTELLIGENT RESPONSE MODES (CHẾ ĐỘ TRẢ LỜI)
Dựa vào câu hỏi của người dùng, hãy chọn 1 trong 2 chế độ sau:

### MODE A: KHI USER CẦN TƯ VẤN THỰC ĐƠN (Gợi ý, ăn gì, thực đơn...)
*Áp dụng khi câu hỏi là: "Ăn gì để giảm cân?", "Thực đơn tăng cơ", "Sáng nay ăn gì?"*

1.  **Tiêu đề:** ## ⚡ Gợi ý Thực đơn [MỤC TIÊU CỦA USER]
2.  **Logic chọn món:** Chọn ra **Top 5-8 món tốt nhất** trong Context phù hợp với mục tiêu (Vd: Giảm cân chọn món ít Calo/nhiều Đạm).
3.  **Format:**
    1. **[Tên Món Đã Chuẩn Hóa]**
       - 📊 Dinh dưỡng (100g): [Số liệu] kcal | Protein: [Số liệu]g
       - 💡 Tại sao chọn: [Lý do ngắn gọn: Giàu đạm/Ít béo/Carb chậm...]

### MODE B: KHI USER HỎI THÔNG TIN CỤ THỂ (Tra cứu)
*Áp dụng khi câu hỏi là: "Phở bò bao nhiêu calo?", "Ức gà có tốt không?", "So sánh A và B"*

1.  **Trả lời trực tiếp:** Cung cấp thông tin dinh dưỡng chính xác từ Context.
2.  **Đánh giá Gym:** Phân tích xem món đó có tốt cho mục tiêu hiện tại không (Cutting hay Bulking).
3.  **Format:**
    - **[Tên Món]**: [Số liệu] kcal | [Số liệu] Protein.
    - **Đánh giá:** [Nhận xét chuyên môn].

### MODE C: KHI USER HỎI LÝ THUYẾT / CÁCH TÍNH
*Áp dụng: "Cách tính macro", "Tập xong nên ăn gì?", "TDEE là gì?"*
1. Giải thích ngắn gọn, dễ hiểu.
2. Cung cấp công thức hoặc nguyên tắc.
3. Ví dụ: "Để tính Macro đơn giản: Protein = 2g * Cân nặng..."
---

# VÍ DỤ MINH HỌA (FEW-SHOT)

**User:** "Ăn gì để siết cơ (Cutting)?"
**AI (Mode A):**
"## ⚡ Gợi ý Thực đơn Siết Cơ (Cutting)
Dựa trên dữ liệu, đây là những lựa chọn giàu đạm, ít mỡ nhất cho bạn:
1. **Ức gà luộc**
   - 📊 Dinh dưỡng: 165 kcal | Protein: 31g
   - 💡 Tại sao chọn: Vua của thực phẩm giảm mỡ, lượng đạm cực cao.
2. **Lòng trắng trứng chiên**
   - 📊 Dinh dưỡng: 52 kcal | Protein: 11g
   - 💡 Tại sao chọn: Calo thấp, không chứa chất béo."

**User:** "Thịt ba chỉ có tốt không?"
**AI (Mode B):**
"Dựa trên dữ liệu:
- **Thịt ba chỉ (Heo)**: Chứa khoảng 518 kcal và chỉ 9g Protein trên 100g, nhưng có tới 53g Chất béo.
- **Đánh giá:** ❌ Không tốt cho tập Gym, đặc biệt là giảm cân. Lượng mỡ quá cao so với lượng đạm. Bạn nên thay bằng thịt thăn hoặc nạc vai."

**User:** "Cách tính TDEE như thế nào?"
**AI (Mode C):**
"Để tính TDEE (Tổng năng lượng tiêu thụ mỗi ngày), bạn cần xác định BMR trước, sau đó nhân với hệ số vận động.
Công thức Harris-Benedict sửa đổi:
1. **Nam:** BMR = 88.362 + (13.397 x kg) + (4.799 x cm) - (5.677 x tuổi)
2. **Nữ:** BMR = 447.593 + (9.247 x kg) + (3.098 x cm) - (4.330 x tuổi)
Sau đó nhân BMR với hệ số (ví dụ: x1.55 nếu tập vừa phải).
💡 Bạn có muốn tôi giúp tính luôn không? Hãy cho tôi biết chiều cao, cân nặng, tuổi và tần suất tập luyện của bạn."
"""

@router.post("/chat")
async def chat_v2(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    API V2 Hybrid Search + Cache + History + Session Management
    """
    try:
        # ====================================================
        # 1. XỬ LÝ SESSION (QUAN TRỌNG: PHẢI LÀM ĐẦU TIÊN)
        # ====================================================
        history_service = HistoryService(db_session=db)
        session_id = request.session_id

        # Nếu chưa có session_id, tạo mới ngay lập tức
        if not session_id:
            session_id = history_service.create_session(current_user['id'], request.question)

        # ====================================================
        # 2. VECTOR & CACHE
        # ====================================================
        query_dense = embedder.embed_dense(request.question)
        query_sparse = embedder.embed_sparse(request.question)

        cached_answer = cache_service.check_cache(query_dense)
        
        if cached_answer:
            emb_model_name = getattr(embedder, "model_name", "unknown-model")
            
            # [QUAN TRỌNG] Ngay cả khi Cache Hit, vẫn phải lưu vào Lịch sử Chat
            # để người dùng thấy tin nhắn này trong Sidebar
            background_tasks.add_task(
                history_service.save_interaction, 
                user_id=current_user['id'],
                session_id=session_id, # Đã có giá trị ở bước 1
                question=request.question, 
                answer=cached_answer, 
                sources=["Cache Hit"]
            )

            # Trả về kết quả Cache kèm session_id
            response_data = {
                "answer": cached_answer,
                "session_id": session_id, # Trả về để Frontend cập nhật URL
                "backend_llm": "semantic_cache",
                "backend_embedding": emb_model_name,
                "context_used": ["Dữ liệu lấy từ Cache."],
            }
            return success_response(data=response_data, message="Lấy từ Cache thành công.")

        # ====================================================
        # 3. HYBRID SEARCH (CACHE MISS)
        # ====================================================
        search_result = qdrant_client.query_points(
            collection_name=COLLECTION_NAME_V2,
            prefetch=[
                models.Prefetch(query=query_dense, using="dense", limit=100),
                models.Prefetch(query=query_sparse.as_object(), using="sparse", limit=100),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=30,
        )

        # Xử lý khi không tìm thấy
        if not search_result.points:
            # Vẫn nên lưu câu hỏi này vào lịch sử dù không tìm thấy
            empty_answer = "Xin lỗi, tôi chưa tìm thấy thông tin về món này trong dữ liệu."
            background_tasks.add_task(
                history_service.save_interaction, 
                user_id=current_user['id'],
                session_id=session_id,
                question=request.question, 
                answer=empty_answer, 
                sources=[]
            )
            
            return success_response(data={
                "answer": empty_answer,
                "session_id": session_id,
                "context_used": []
            }, message="Không tìm thấy dữ liệu.")

        context_list = [hit.payload["content"] for hit in search_result.points]
        context = "\n".join(context_list)

        # ====================================================
        # 4. GENERATE ANSWER (LLM)
        # ====================================================
        final_prompt = f"""
        {HARDCORE_SYSTEM_PROMPT}
        
        ==============
        CONTEXT DỮ LIỆU:
        {context}
        ==============
        
        CÂU HỎI CỦA NGƯỜI DÙNG: "{request.question}"
        
        TRẢ LỜI (TUÂN THỦ STRICT RULES):
        """

        answer = llm_service.generate_answer(final_prompt)

        # ====================================================
        # 5. SAVE HISTORY & CACHE
        # ====================================================
        # Lưu lịch sử chạy ngầm
        background_tasks.add_task(
            history_service.save_interaction, 
            user_id=current_user['id'],
            session_id=session_id, # Đã có giá trị
            question=request.question, 
            answer=answer, 
            sources=context_list
        )
        
        # Lưu Cache vector
        cache_service.save_to_cache(query_dense, request.question, answer)

        # ====================================================
        # 6. RESPONSE
        # ====================================================
        emb_model_name = getattr(embedder, "model_name", "unknown-model")
        response_data = {
            "answer": answer,
            "session_id": session_id, # Trả về để Frontend cập nhật
            "backend_llm": llm_service.backend,
            "backend_embedding": emb_model_name,
            "context_used": context_list
        }
        
        return success_response(data=response_data, message="Trả lời thành công.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))