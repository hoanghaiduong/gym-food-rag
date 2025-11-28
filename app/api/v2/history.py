# app/api/v2/history.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.services.history_service import HistoryService
from app.models.schemas import ChatHistoryItem
from app.core.response import success_response

router = APIRouter()

# --- 1. LẤY DANH SÁCH LỊCH SỬ (FLAT LIST - Cũ/Optional) ---
# Bạn có thể giữ lại để xem toàn bộ log, hoặc bỏ đi nếu chỉ dùng Session
@router.get("/", response_model=dict)
async def get_my_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xem toàn bộ lịch sử chat (Flat List)"""
    service = HistoryService(db)
    # [FIX] Truy cập bằng ['id']
    history = service.get_user_history(current_user['id'], limit, offset)
    
    data = [ChatHistoryItem(**row).model_dump() for row in history]
    return success_response(data=data, message="Lấy lịch sử chat thành công.")

# --- 2. LẤY DANH SÁCH HỘI THOẠI (SESSION LIST - Mới/Sidebar) ---
@router.get("/sessions")
async def get_sessions(
    limit: int = 20, 
    offset: int = 0, 
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Lấy danh sách các cuộc hội thoại (cho Sidebar)"""
    service = HistoryService(db)
    # [FIX] Truy cập bằng ['id']
    sessions = service.get_user_sessions(current_user['id'], limit, offset)
    return success_response(data=sessions)

# --- 3. LẤY CHI TIẾT 1 HỘI THOẠI ---
@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """Lấy toàn bộ nội dung chat của 1 session"""
    service = HistoryService(db)
    # [FIX] Truy cập bằng ['id']
    messages = service.get_session_messages(session_id, current_user['id'])
    
    if messages is None:
        raise HTTPException(404, "Hội thoại không tồn tại hoặc không có quyền truy cập")
    
    return success_response(data=messages)

# --- 4. XÓA LỊCH SỬ ---
@router.delete("/clear", response_model=dict)
async def clear_my_history(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Xóa toàn bộ lịch sử chat"""
    service = HistoryService(db)
    
    # [FIX QUAN TRỌNG] Đổi .id thành ['id']
    count = service.clear_user_history(current_user['id'])
    
    return success_response(data={"deleted_rows": count}, message="Đã xóa toàn bộ lịch sử chat.")