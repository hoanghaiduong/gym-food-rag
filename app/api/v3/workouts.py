from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, success_response
from app.schemas.workout_logs import WorkoutLogCreate, WorkoutLogResponse, WorkoutLogSummaryResponse, WorkoutLogUpdate
from app.services.workout_log_service import workout_log_service


router = APIRouter()


@router.post("/logs", response_model=BaseResponse[WorkoutLogResponse])
async def create_workout_log(
    payload: WorkoutLogCreate,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    data = workout_log_service.create(db, user_id=current_user["id"], payload=payload)
    return success_response(data=data, message="Tạo nhật ký buổi tập thành công.")


@router.get("/logs", response_model=BaseResponse[list[WorkoutLogResponse]])
async def list_workout_logs(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    data = workout_log_service.list(db, user_id=current_user["id"], date_from=date_from, date_to=date_to)
    return success_response(data=data, message="Lấy nhật ký buổi tập thành công.")


@router.get("/logs/summary", response_model=BaseResponse[WorkoutLogSummaryResponse])
async def summarize_workout_logs(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    data = workout_log_service.summary(db, user_id=current_user["id"], date_from=date_from, date_to=date_to)
    return success_response(data=data, message="Tổng hợp nhật ký buổi tập thành công.")


@router.get("/logs/{log_id}", response_model=BaseResponse[WorkoutLogResponse])
async def get_workout_log(
    log_id: int,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        return success_response(data=workout_log_service.get(db, user_id=current_user["id"], log_id=log_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/logs/{log_id}", response_model=BaseResponse[WorkoutLogResponse])
async def update_workout_log(
    log_id: int,
    payload: WorkoutLogUpdate,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        data = workout_log_service.update(db, user_id=current_user["id"], log_id=log_id, payload=payload)
        return success_response(data=data, message="Cập nhật nhật ký buổi tập thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/logs/{log_id}", response_model=BaseResponse[dict])
async def delete_workout_log(
    log_id: int,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        workout_log_service.delete(db, user_id=current_user["id"], log_id=log_id)
        return success_response(data={"deleted": True}, message="Xóa nhật ký buổi tập thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
