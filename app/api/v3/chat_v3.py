from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

# Import các dependency và service
from app.api.deps import get_db, get_current_user
from app.core.response import success_response
from app.services.v3.agent import agent_service_v3
from app.services.history_service import HistoryService

router = APIRouter()

class ChatRequestV3(BaseModel):
    question: str
    session_id: Optional[str] = None

@router.post("/chat")
async def chat_agent_v3(
    request: ChatRequestV3,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    API V3: LangGraph Agent + Redis Memory + Postgres History.
    """
    try:
        # Khởi tạo service lịch sử với DB session hiện tại
        history_service = HistoryService(db_session=db)
        
        # 1. Xử lý Session (Tạo mới nếu chưa có)
        session_id = request.session_id
        if not session_id:
            # Tạo session trong Postgres để hiển thị bên Sidebar
            session_id = history_service.create_session(current_user['id'], request.question)

        # 2. Gọi Agent (LangGraph)
        # Agent sẽ tự động dùng session_id để truy xuất bộ nhớ ngắn hạn từ Redis
        answer = await agent_service_v3.process_question(session_id, request.question)

        # 3. Lưu Lịch sử vào Postgres (Chạy ngầm)
        # Để người dùng có thể xem lại lịch sử chat sau này (Long-term memory)
        background_tasks.add_task(
            history_service.save_interaction, 
            user_id=current_user['id'],
            session_id=session_id,
            question=request.question, 
            answer=answer, 
            sources=["Agent V3 (LangGraph)"] # Agent tự động nên khó track source chi tiết hơn V2
        )

        return success_response(
            data={
                "answer": answer,
                "session_id": session_id,
                "agent_engine": "LangGraph + Redis",
            },
            message="Thành công"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))