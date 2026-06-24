from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import PermissionChecker
from app.core.response import BaseResponse, success_response
from app.schemas.training import (
    TrainingOptionsResponse,
    TrainingRecommendationRequest,
    TrainingRecommendationResponse,
)
from app.services.training_plan_service import training_plan_service


router = APIRouter()


@router.get("/options", response_model=BaseResponse[TrainingOptionsResponse])
async def get_training_options():
    return success_response(
        data=training_plan_service.build_options(),
        message="Lấy tùy chọn tập luyện thành công.",
    )


@router.post("/recommendation", response_model=BaseResponse[TrainingRecommendationResponse])
async def generate_training_recommendation(
    payload: TrainingRecommendationRequest,
    current_user=Depends(PermissionChecker("user.profile")),
):
    try:
        result = training_plan_service.build_recommendation(dict(current_user), payload)
        return success_response(data=result, message="Tạo khuyến nghị tập luyện thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
