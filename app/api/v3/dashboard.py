from fastapi import APIRouter, Depends

from app.api.deps import PermissionChecker
from app.core.response import BaseResponse, success_response
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard_overview_service import dashboard_overview_service


router = APIRouter()


@router.get("/overview", response_model=BaseResponse[DashboardOverviewResponse])
async def get_dashboard_overview(
    current_user=Depends(PermissionChecker("user.profile")),
):
    overview = dashboard_overview_service.build_overview(dict(current_user))
    return success_response(data=overview, message="Lấy tổng quan dashboard thành công.")
