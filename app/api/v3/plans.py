from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import PermissionChecker
from app.core.response import BaseResponse, success_response
from app.schemas.plans import MonthlyPlansResponse, WeeklyTimelineItem
from app.services.plans_service import plans_service


router = APIRouter()


@router.get("/weekly", response_model=BaseResponse[list[WeeklyTimelineItem]])
async def get_weekly_plans(
    week_start: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("user.profile")),
):
    data = plans_service.build_weekly(dict(current_user), week_start=week_start)
    return success_response(data=data, message="Lấy lịch tuần thành công.")


@router.get("/monthly", response_model=BaseResponse[MonthlyPlansResponse])
async def get_monthly_plans(
    year: int = Query(..., ge=1900, le=2200),
    month: int = Query(..., ge=1, le=12),
    current_user=Depends(PermissionChecker("user.profile")),
):
    data = plans_service.build_monthly(dict(current_user), year=year, month=month)
    return success_response(data=data, message="Lấy lịch tháng thành công.")
