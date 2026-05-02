from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, SessionLocal, get_db
from app.core.response import BaseResponse, success_response
from app.schemas.chat import ChatRequest, ChatResponseV3
from app.services.general_chat_service import general_chat_service
from app.services.history_service import HistoryService


router = APIRouter()


@router.post("", response_model=BaseResponse[ChatResponseV3], summary="General safe chat")
async def chat_v3(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(PermissionChecker("chat.use")),
    db: Session = Depends(get_db),
):
    """General chat endpoint.

    This endpoint does not generate meal plans. Personalized nutrition requests are
    routed to `/api/v3/nutrition/recommendation-agent`, where the validated core
    recommendation engine owns final food selection.
    """
    history_service = HistoryService(db_session=db)
    session_id = _resolve_session_id(history_service, request, current_user["id"])

    result = general_chat_service.answer(
        question=request.question,
        current_user=dict(current_user),
    )
    payload = result.to_dict()
    payload["session_id"] = session_id

    background_tasks.add_task(
        _save_chat_interaction,
        user_id=current_user["id"],
        session_id=session_id,
        question=request.question,
        answer=result.answer,
        sources=[result.engine, *result.context_used],
    )

    return success_response(data=payload, message="Chat processed successfully.")


async def _save_chat_interaction(
    *,
    user_id: int,
    session_id: str,
    question: str,
    answer: str,
    sources: list[str],
) -> None:
    db = SessionLocal()
    await HistoryService(db_session=db).save_interaction(
        user_id=user_id,
        session_id=session_id,
        question=question,
        answer=answer,
        sources=sources,
    )


def _resolve_session_id(
    history_service: HistoryService,
    request: ChatRequest,
    user_id: int,
) -> str:
    if not request.session_id:
        return history_service.create_session(user_id, request.question)

    messages = history_service.get_session_messages(request.session_id, user_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return request.session_id
