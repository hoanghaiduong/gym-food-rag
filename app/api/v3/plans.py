from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, success_response
from app.schemas.plans import MonthlyPlansResponse, WeeklyTimelineItem
from app.schemas.saved_plans import (
    MonthlyPlanGenerateRequest,
    SavedPlanCreate,
    SavedPlanResponse,
    SavedPlanUpdate,
    WeeklyPlanGenerateRequest,
)
from app.services.plan_persistence_service import plan_persistence_service
from app.services.plans_service import plans_service


router = APIRouter()


@router.get("/weekly", response_model=BaseResponse[list[WeeklyTimelineItem]])
async def get_weekly_plans(
    week_start: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    effective_start = week_start or plans_service._start_of_week(plans_service._today())
    data = plan_persistence_service.get_weekly_timeline(
        db,
        user_id=current_user["id"],
        week_start=effective_start,
    ) or plans_service.build_weekly(dict(current_user), week_start=effective_start)
    return success_response(data=data, message="Lấy lịch tuần thành công.")


@router.get("/monthly", response_model=BaseResponse[MonthlyPlansResponse])
async def get_monthly_plans(
    year: int = Query(..., ge=1900, le=2200),
    month: int = Query(..., ge=1, le=12),
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    data = plan_persistence_service.get_monthly_overview(
        db,
        user_id=current_user["id"],
        year=year,
        month=month,
    ) or plans_service.build_monthly(dict(current_user), year=year, month=month)
    return success_response(data=data, message="Lấy lịch tháng thành công.")


@router.post("/saved", response_model=BaseResponse[SavedPlanResponse])
async def create_saved_plan(
    payload: SavedPlanCreate,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        data = plan_persistence_service.create(db, user_id=current_user["id"], payload=payload)
        return success_response(data=data, message="Lưu kế hoạch thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/saved", response_model=BaseResponse[list[SavedPlanResponse]])
async def list_saved_plans(
    plan_type: Optional[str] = Query(default=None, alias="type"),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    data = plan_persistence_service.list(
        db,
        user_id=current_user["id"],
        plan_type=plan_type,
        date_from=date_from,
        date_to=date_to,
    )
    return success_response(data=data, message="Lấy danh sách kế hoạch đã lưu thành công.")


@router.get("/saved/{plan_id}", response_model=BaseResponse[SavedPlanResponse])
async def get_saved_plan(
    plan_id: int,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        return success_response(data=plan_persistence_service.get(db, user_id=current_user["id"], plan_id=plan_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/saved/{plan_id}", response_model=BaseResponse[SavedPlanResponse])
async def update_saved_plan(
    plan_id: int,
    payload: SavedPlanUpdate,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        data = plan_persistence_service.update(db, user_id=current_user["id"], plan_id=plan_id, payload=payload)
        return success_response(data=data, message="Cập nhật kế hoạch đã lưu thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/saved/{plan_id}", response_model=BaseResponse[dict])
async def delete_saved_plan(
    plan_id: int,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        plan_persistence_service.delete(db, user_id=current_user["id"], plan_id=plan_id)
        return success_response(data={"deleted": True}, message="Xóa kế hoạch đã lưu thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/weekly/generate", response_model=BaseResponse[SavedPlanResponse])
async def generate_weekly_plan(
    payload: WeeklyPlanGenerateRequest,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        data = plan_persistence_service.generate_weekly(db, current_user=dict(current_user), payload=payload)
        return success_response(data=data, message="Tạo và lưu kế hoạch tuần thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/monthly/generate", response_model=BaseResponse[SavedPlanResponse])
async def generate_monthly_plan(
    payload: MonthlyPlanGenerateRequest,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    try:
        data = plan_persistence_service.generate_monthly(db, current_user=dict(current_user), payload=payload)
        return success_response(data=data, message="Tạo và lưu kế hoạch tháng thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
