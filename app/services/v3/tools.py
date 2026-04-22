import os
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Import service Embedding cũ (để tái sử dụng logic embed)
from app.services.embedding_bge_service import get_bge_service
from app.services.nutrition_service import NutritionService
from typing import List

# --- CONFIG ---
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("COLLECTION_NAME_ACTIVE") or os.getenv("COLLECTION_NAME", "gym_food_hybrid_v1")

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
        hybrid_query = embedder.encode_hybrid(query)
        dense_vector = hybrid_query.dense
        sparse_vector = hybrid_query.sparse
        
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

@tool
def optimize_meal_plan(food_keywords: List[str], target_calories: float, target_protein: float, target_carbs: float, target_fat: float):
    """
    CÔNG CỤ NÀY PHẢI ĐƯỢC GỌI ĐỂ TÍNH TOÁN LƯỢNG GRAM MÓN ĂN KHI TẠO THỰC ĐƠN.
    Input:
        - food_keywords (list[str]): Danh sách các món ăn muốn đưa vào bữa ăn (VD: ["cơm trắng", "ức gà luộc", "rau muống"]).
        - target_calories (float): Mục tiêu năng lượng của toàn bữa (Tự lấy từ System Context hoặc chia ra theo bữa sáng/trưa/tối).
        - target_protein, target_carbs, target_fat: Mục tiêu dinh dưỡng (Từ System Context rải ra cho bữa ăn).
    Output:
        Trả về kết quả chính xác số gram (weight) cho từng món để bám sát mục tiêu.
    """
    print(f"⚖️ [Optimization Tool] Gọi Solver cho list: {food_keywords}")
    
    # B1. Tìm kiếm thông tin thực phẩm cho từng món
    available_foods = []
    for food in food_keywords:
        dense_vector = embedder.encode_hybrid(food).dense
        # Tìm 1 món chuẩn nhất
        search_result = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=("dense", dense_vector),
            limit=1
        )
        if search_result:
            payload = search_result[0].payload
            # Chuẩn hóa cấu trúc
            extracted_food = {
                'name': payload.get('name', food),
                'calories': payload.get('energy_kcal', payload.get('calories', 0)),
                'protein': payload.get('protein_g', payload.get('protein', 0)),
                'carbs': payload.get('carbs_g', payload.get('carbs', 0)),
                'fat': payload.get('fat_g', payload.get('fat', 0))
            }
            available_foods.append(extracted_food)
            
    if not available_foods:
        return "SYSTEM_MSG: Không tìm thấy thông tin trên hệ thống đê cân bằng năng lượng."
        
    # B2. Gọi Scipy Optimization
    target_macros = {
        'calories': target_calories,
        'protein': target_protein,
        'carbs': target_carbs,
        'fat': target_fat
    }
    
    optimized_result = NutritionService.optimize_meal(available_foods, target_macros)
    
    # B3. Định dạng văn bản trả về cho LLM
    text_res = "KẾT QUẢ TÍNH TOÁN (Hãy bê nguyên si gram này vào câu trả lời, đừng tự tính):\n"
    total_cal = total_pro = total_carb = total_fat = 0
    
    for item in optimized_result:
        text_res += f"- {item['name']}: {item['calculated_grams']}g (Calo: {item['calculated_calories']} kcal, Pro: {item['calculated_protein']}g, Carb: {item['calculated_carbs']}g, Fat: {item['calculated_fat']}g)\n"
        total_cal += item['calculated_calories']
        total_pro += item['calculated_protein']
        total_carb += item['calculated_carbs']
        total_fat += item['calculated_fat']
        
    text_res += f"\nTỔNG BỮA NÀY: {total_cal:.1f} kcal | Pro: {total_pro:.1f}g | Carb: {total_carb:.1f}g | Fat: {total_fat:.1f}g"
    return text_res

# Export danh sách tools
agent_tools = [search_gym_food, optimize_meal_plan]
