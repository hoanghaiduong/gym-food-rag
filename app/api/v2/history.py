# app/api/v2/history.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.services.history_service import HistoryService
from app.models.schemas import ChatHistoryItem
from app.core.response import success_response

router = APIRouter()

@router.get("/", response_model=dict) # Trả về dict bọc data
async def get_my_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xem lịch sử chat của chính mình (Có phân trang)"""
    service = HistoryService(db)
    history = service.get_user_history(current_user["id"], limit, offset)
    
    # Convert sang list Pydantic manual nếu cần hoặc trả về thẳng
    data = [ChatHistoryItem(**row).model_dump() for row in history]
    
    return success_response(data=data, message="Lấy lịch sử chat thành công.")

@router.delete("/clear", response_model=dict)
async def clear_my_history(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xóa toàn bộ lịch sử chat"""
    service = HistoryService(db)
    count = service.clear_user_history(current_user.id)
    
    return success_response(data={"deleted_rows": count}, message="Đã xóa toàn bộ lịch sử chat.")