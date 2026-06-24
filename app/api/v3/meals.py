from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, success_response
from app.schemas.meal_logs import MealLogCreate, MealLogResponse, MealLogSummaryResponse, MealLogUpdate
from app.services.meal_log_service import meal_log_service


router = APIRouter()


@router.post("/logs", response_model=BaseResponse[MealLogResponse])
async def create_meal_log(
    payload: MealLogCreate,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        data = meal_log_service.create(db, user_id=current_user["id"], payload=payload)
        return success_response(data=data, message="Tạo nhật ký bữa ăn thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/logs", response_model=BaseResponse[list[MealLogResponse]])
async def list_meal_logs(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    data = meal_log_service.list(db, user_id=current_user["id"], date_from=date_from, date_to=date_to)
    return success_response(data=data, message="Lấy nhật ký bữa ăn thành công.")


@router.get("/logs/summary", response_model=BaseResponse[MealLogSummaryResponse])
async def summarize_meal_logs(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    data = meal_log_service.summary(db, user_id=current_user["id"], date_from=date_from, date_to=date_to)
    return success_response(data=data, message="Tổng hợp nhật ký bữa ăn thành công.")


@router.get("/logs/{log_id}", response_model=BaseResponse[MealLogResponse])
async def get_meal_log(
    log_id: int,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        return success_response(data=meal_log_service.get(db, user_id=current_user["id"], log_id=log_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/logs/{log_id}", response_model=BaseResponse[MealLogResponse])
async def update_meal_log(
    log_id: int,
    payload: MealLogUpdate,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        data = meal_log_service.update(db, user_id=current_user["id"], log_id=log_id, payload=payload)
        return success_response(data=data, message="Cập nhật nhật ký bữa ăn thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/logs/{log_id}", response_model=BaseResponse[dict])
async def delete_meal_log(
    log_id: int,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        meal_log_service.delete(db, user_id=current_user["id"], log_id=log_id)
        return success_response(data={"deleted": True}, message="Xóa nhật ký bữa ăn thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
