# from fastapi import APIRouter, HTTPException
# from app.schemas import ChatRequest, ChatResponse
# from app.services.llm_service import llm_service
# from qdrant_client import QdrantClient
# import traceback
# import os

# router = APIRouter()

# # --- CẤU HÌNH RIÊNG CHO V1 ---
# # Bắt buộc dùng Collection cũ để khớp với Gemini Embedding (768 chiều)
# LEGACY_COLLECTION_NAME = "gym_food_collection"

# # Kết nối Qdrant trực tiếp (Bỏ qua vector_db service để tránh đọc nhầm .env)
# QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
# QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
# qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
# SYSTEM_PROMPT = """
# # ROLE (VAI TRÒ)
# Bạn là một Chuyên gia Dinh dưỡng Thể hình Thực chiến (Practical Gym Nutritionist).
# Khách hàng của bạn là người tập Gym cần tư vấn món ăn cụ thể để bỏ vào miệng, KHÔNG PHẢI nhà kho cần kiểm kê nguyên liệu.

# # CRITICAL RULE: DATA TRANSLATION (QUY TẮC SỐNG CÒN - BẮT BUỘC)
# Dữ liệu trong CONTEXT là dạng thô (Raw). Bạn TUYỆT ĐỐI KHÔNG hiển thị nguyên văn tên nguyên liệu thô ra màn hình. Bạn phải thực hiện bước "DỊCH DỮ LIỆU" theo logic sau:

# 1. TỪ ĐIỂN CHUYỂN ĐỔI (MAPPING):
#    - Thấy "Gạo tẻ/nếp... sống" -> BẮT BUỘC đổi thành: "Cơm trắng", "Cháo", hoặc "Xôi".
#    - Thấy "Miến/Mì... khô" -> BẮT BUỘC đổi thành: "Miến nấu", "Mì luộc".
#    - Thấy "Khoai... khô" -> Đổi thành: "Khoai luộc/hấp".
#    - Thấy "Bột..." -> Chỉ gợi ý nếu có thể làm thành bánh (VD: Bánh từ bột gạo), nếu không thì BỎ QUA.
#    - Thấy "Quả... khô" -> Giữ nguyên (vì ăn liền được).

# 2. XỬ LÝ SỐ LIỆU (CALO/MACRO):
#    - Giữ nguyên số liệu Calo/Carb từ Context.
#    - Thêm chú thích nhỏ: *(Số liệu tính trên lượng nguyên liệu thô tương ứng)*.

# # NUTRITION LOGIC (TƯ DUY DINH DƯỠNG)
# 1. PHÂN LOẠI MỤC TIÊU:
#    - Với mục tiêu GIẢM CÂN (Fat Loss): Ưu tiên Carb tiêu hóa chậm (Khoai, Yến mạch, Đậu), trái cây ít đường. Cảnh báo các món mật độ năng lượng quá cao (như Xôi, Hoa quả sấy nhiều đường).
#    - Với mục tiêu PRE-WORKOUT: Chọn món dễ tiêu, giàu Carb để nạp năng lượng nhanh.

# 2. BỘ LỌC THỰC TẾ (REALITY CHECK):
#    - Tuyệt đối không gợi ý: Mỳ tôm (kém lành mạnh), Gạo sống (không ăn được).

# # OUTPUT FORMAT (ĐỊNH DẠNG CÂU TRẢ LỜI)
# Trình bày dưới dạng Menu thực đơn hấp dẫn:

# ## 🍽️ Thực đơn Nạp Năng Lượng Trước Tập (Pre-Workout)
# *(Dựa trên dữ liệu dinh dưỡng)*

# 1. **[Tên Món Đã Nấu Chín]**
#    - 📊 Dinh dưỡng: [Calo] kcal | [Carb]g Carb | [Protein]g Pro
#    - 💡 Tại sao chọn: [Giải thích ngắn gọn lợi ích cho việc tập luyện/giảm cân]

# 2. **[Tên Món Ăn Liền]**
#    ...

# ⚠️ **Lưu ý quan trọng:** [Lời khuyên về khẩu phần để đảm bảo thâm hụt Calo]
# """

# @router.post("/chat", response_model=ChatResponse)
# async def chat_endpoint(request: ChatRequest):
#     try:
#         print(f"--- [V1 Legacy] Nhận câu hỏi: {request.question} ---")
        
#         # 1. Tạo vector bằng Gemini (Legacy method)
#         # Hàm này trong LLMService mới vẫn gọi text-embedding-004 (768 chiều)
#         print("1. Đang tạo vector Gemini (768 dims)...")
#         query_vector = llm_service.get_embedding(request.question)
        
#         if not query_vector:
#             raise HTTPException(status_code=500, detail="Lỗi tạo vector embedding.")

#         # 2. Tìm kiếm trong Collection Cũ (gym_food_collection)
#         print(f"2. Đang tìm trong collection: {LEGACY_COLLECTION_NAME}...")
#         search_results = qdrant_client.search(
#             collection_name=LEGACY_COLLECTION_NAME,
#             query_vector=query_vector,
#             limit=5
#         )
#         print(f"   -> Tìm thấy {len(search_results)} kết quả.")
        
#         # 3. Xây dựng Context
#         sources = []
#         context_text = ""
        
#         if not search_results:
#             context_text = "Không tìm thấy dữ liệu món ăn nào phù hợp."
#         else:
#             # Chuyển đổi format Qdrant sang dict để trả về API
#             context_items = []
#             for hit in search_results:
#                 payload = hit.payload
#                 context_items.append(f"Món: {payload.get('name')} - {payload.get('content')}")
#                 sources.append(payload) # Lưu lại source để trả về frontend
            
#             context_text = "\n---\n".join(context_items)
        
#         # 4. Gửi cho LLM
#         # Dù V1 cũ dùng Gemini, nhưng nhờ LLMService mới,
#         # nó sẽ tự động dùng Gemini hoặc Ollama tùy theo bạn set LLM_BACKEND trong .env
#         # (Rất tiện: Dữ liệu cũ nhưng bộ não trả lời có thể là Llama 3 mới)
#         print("3. Đang sinh câu trả lời...")
#         answer = llm_service.generate_response(
#             system_prompt=SYSTEM_PROMPT,
#             user_question=request.question,
#             context=context_text
#         )
        
#         return ChatResponse(
#             answer=answer,
#             sources=sources
#         )

#     except Exception as e:
#         print("-------------------- START ERROR TRACEBACK --------------------")
#         traceback.print_exc() 
#         print("-------------------- END ERROR TRACEBACK --------------------")
#         raise HTTPException(status_code=500, detail=str(e))