from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, success_response
from app.schemas.ai_control import AIFeedbackCreate, AIFeedbackResponse
from app.services.ai_control_service import ai_control_service


router = APIRouter()


@router.post("/feedback", response_model=BaseResponse[AIFeedbackResponse])
async def create_ai_feedback(
    payload: AIFeedbackCreate,
    current_user=Depends(PermissionChecker("chat.use")),
    db: Session = Depends(get_db),
):
    data = ai_control_service.create_feedback(db, user_id=current_user["id"], payload=payload)
    return success_response(data=data, message="Ghi nhận phản hồi AI thành công.")
