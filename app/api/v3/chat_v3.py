from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

# Import Dependencies & Services
from app.api.deps import get_db, get_current_user, PermissionChecker
from app.core.response import success_response
from app.services.history_service import HistoryService
from app.services.cache_service import cache_service
from app.services.embedding_bge_service import get_bge_service
from app.services.nutrition_intent_service import nutrition_intent_service

# Import Agent V3
from app.services.v3.agent import agent_service_v3
from app.services.nutrition_service import NutritionService

router = APIRouter()
embedder = get_bge_service()  # Singleton Embedder

class ChatRequestV3(BaseModel):
    question: str
    session_id: Optional[str] = None

@router.post("/chat")
async def chat_agent_v3(
    request: ChatRequestV3,
    background_tasks: BackgroundTasks,
    current_user = Depends(PermissionChecker("chat.use")),
    db: Session = Depends(get_db)
):
    """
    API V3: Hybrid Architecture
    Flow: User -> Redis Cache (Dense Check) -> [Miss] -> Agent (Ollama + Tool Hybrid Search)
    """
    try:
        history_service = HistoryService(db_session=db)
        
        # 1. Quản lý Session
        session_id = request.session_id
        if not session_id:
            session_id = history_service.create_session(current_user['id'], request.question)

        user_dict = dict(current_user)
        clarification = nutrition_intent_service.get_chat_clarification(user_dict, request.question)
        if clarification:
            answer = clarification["question"]
            background_tasks.add_task(
                history_service.save_interaction,
                user_id=current_user['id'],
                session_id=session_id,
                question=request.question,
                answer=answer,
                sources=["Nutrition Intent Clarifier"]
            )
            return success_response(
                data={
                    "answer": answer,
                    "session_id": session_id,
                    "engine": "Nutrition Intent Clarifier",
                    "context_used": [],
                    "clarification": clarification,
                },
                message="Cần làm rõ ý định trước khi tư vấn."
            )

        # ====================================================
        # 2. LỚP CACHE (TỐC ĐỘ CAO)
        # ====================================================
        # Chỉ dùng Dense Embedding để check Cache cho nhanh (Tiết kiệm tài nguyên)
        query_dense = embedder.embed_dense(request.question)
        cached_answer = cache_service.check_cache(query_dense)

        if cached_answer:
            # --- CACHE HIT ---
            # Lưu log để hiển thị history
            background_tasks.add_task(
                history_service.save_interaction,
                user_id=current_user['id'],
                session_id=session_id,
                question=request.question,
                answer=cached_answer,
                sources=["Redis Semantic Cache"]
            )
            return success_response(
                data={
                    "answer": cached_answer,
                    "session_id": session_id,
                    "engine": "Redis Cache (Fast)",
                    "context_used": []
                },
                message="Trả về từ Cache."
            )

        # ====================================================
        # 3. LỚP AGENT (THÔNG MINH - LOCAL LLM)
        # ====================================================
        # A. Chuẩn bị User Profile
        user_dict = dict(current_user)
        # Tính toán TDEE và Macros nếu đủ dữ liệu
        if user_dict.get('weight') and user_dict.get('height') and user_dict.get('age') and user_dict.get('gender'):
            try:
                tdee = NutritionService.calculate_tdee(
                    age=user_dict['age'],
                    gender=user_dict['gender'],
                    weight=user_dict['weight'],
                    height=user_dict['height'],
                    activity_level=user_dict.get('activity_level', 'moderate')
                )
                user_dict['tdee'] = round(tdee, 0)
                
                goal = user_dict.get('target_goal', 'maintain')
                dietary = user_dict.get('dietary_preference', 'omnivore')
                user_dict['macros'] = NutritionService.get_macro_targets(
                    tdee, goal, dietary, user_dict.get('weight')
                )
            except Exception as e:
                print(f"Error calculating TDEE: {e}")

        # B. Gọi Agent xử lý
        answer = await agent_service_v3.process_question(session_id, request.question, user_dict)

        # ====================================================
        # 4. HẬU XỬ LÝ (LƯU LẠI)
        # ====================================================
        # A. Lưu Cache mới (Dense Key)
        cache_service.save_to_cache(query_dense, request.question, answer)

        # B. Lưu lịch sử DB
        background_tasks.add_task(
            history_service.save_interaction,
            user_id=current_user['id'],
            session_id=session_id,
            question=request.question,
            answer=answer,
            sources=["Agent V3 (LangGraph + Ollama)"]
        )

        return success_response(
            data={
                "answer": answer,
                "session_id": session_id,
                "engine": "LangGraph Agent + Ollama",
                "context_used": ["Dynamic Tool Search"]
            },
            message="Thành công."
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
