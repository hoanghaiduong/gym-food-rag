import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, success_response
from app.db.tables import users
from app.schemas.nutrition import (
    NutritionAgentRecommendationRequest,
    NutritionAgentRecommendationResponse,
    NutritionEvaluationResponse,
    NutritionOptionsResponse,
    NutritionProfile,
    NutritionProfileUpdate,
    NutritionRecommendationRequest,
    NutritionRecommendationResponse,
    WorkflowStateResponse,
)
from app.core.config import settings
from app.services.nutrition_evaluation_service import nutrition_evaluation_service
from app.services.nutrition.orchestration import nutrition_agent_service
from app.services.nutrition_workflow_service import nutrition_workflow_service
from app.services.redis_state_service import redis_state_service


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/options", response_model=BaseResponse[NutritionOptionsResponse])
async def get_nutrition_options():
    options = {
        "goals": [
            {"value": "gain-muscle", "label": "Tăng cơ", "backend_value": "gain_muscle"},
            {"value": "lose-fat", "label": "Giảm mỡ", "backend_value": "lose_weight"},
            {"value": "maintain", "label": "Duy trì", "backend_value": "maintain"},
        ],
        "activity_levels": [
            {"value": "sedentary", "label": "Ít vận động", "backend_value": "sedentary"},
            {"value": "light", "label": "Vận động nhẹ", "backend_value": "light"},
            {"value": "moderate", "label": "Vận động vừa", "backend_value": "moderate"},
            {"value": "active", "label": "Năng động", "backend_value": "active"},
            {"value": "very_active", "label": "Rất năng động", "backend_value": "very_active"},
        ],
        "diet_styles": [
            {"value": "balanced", "label": "Cân bằng", "backend_value": "omnivore"},
            {"value": "vegetarian", "label": "Ăn chay", "backend_value": "vegetarian"},
            {"value": "vegan", "label": "Thuần chay", "backend_value": "vegan"},
            {"value": "pescatarian", "label": "Ăn cá", "backend_value": "pescatarian"},
            {"value": "keto", "label": "Keto", "backend_value": "omnivore"},
            {"value": "paleo", "label": "Paleo", "backend_value": "omnivore"},
        ],
        "allergies": [
            {"value": "dairy", "label": "Sữa", "backend_value": "dairy"},
            {"value": "egg", "label": "Trứng", "backend_value": "egg"},
            {"value": "soy", "label": "Đậu nành", "backend_value": "soy"},
            {"value": "peanut", "label": "Lạc/đậu phộng", "backend_value": "peanut"},
            {"value": "tree_nut", "label": "Hạt cây", "backend_value": "tree_nut"},
            {"value": "gluten", "label": "Gluten", "backend_value": "gluten"},
            {"value": "shellfish", "label": "Tôm cua/giáp xác", "backend_value": "shellfish"},
            {"value": "fish", "label": "Cá", "backend_value": "fish"},
            {"value": "sesame", "label": "Mè", "backend_value": "sesame"},
        ],
        "training_types": [
            {"value": "gym", "label": "Gym", "backend_value": "gym"},
            {"value": "cardio", "label": "Cardio", "backend_value": "cardio"},
            {"value": "yoga", "label": "Yoga", "backend_value": "yoga"},
            {"value": "running", "label": "Chạy bộ", "backend_value": "running"},
            {"value": "calisthenics", "label": "Calisthenics", "backend_value": "calisthenics"},
        ],
    }
    return success_response(data=options, message="Lấy tùy chọn dinh dưỡng thành công.")


@router.get("/profile", response_model=BaseResponse[NutritionProfile])
async def get_my_nutrition_profile(
    current_user=Depends(PermissionChecker("user.profile")),
):
    profile = nutrition_workflow_service.build_profile(dict(current_user))
    return success_response(data=profile, message="Lấy hồ sơ dinh dưỡng thành công.")


@router.put("/profile", response_model=BaseResponse[NutritionProfile])
async def update_my_nutrition_profile(
    payload: NutritionProfileUpdate,
    current_user=Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db),
):
    update_data = nutrition_workflow_service.normalize_profile_update(
        payload.model_dump(exclude_none=True)
    )
    if not update_data:
        profile = nutrition_workflow_service.build_profile(dict(current_user))
        return success_response(data=profile, message="Không có trường hồ sơ dinh dưỡng nào được thay đổi.")

    db.execute(
        update(users)
        .where(users.c.id == current_user["id"])
        .values(**update_data)
    )
    db.commit()

    updated_user = db.execute(
        select(users).where(users.c.id == current_user["id"])
    ).mappings().fetchone()
    profile = nutrition_workflow_service.build_profile(dict(updated_user))
    return success_response(data=profile, message="Cập nhật hồ sơ dinh dưỡng thành công.")


@router.post("/recommendation", response_model=BaseResponse[NutritionRecommendationResponse])
async def generate_nutrition_recommendation(
    payload: NutritionRecommendationRequest,
    current_user=Depends(PermissionChecker("chat.use")),
):
    try:
        logger.info(
            "Nutrition recommendation started | user_id=%s | meal_count=%s | top_k=%s | revisions=%s",
            current_user["id"],
            payload.meal_count,
            payload.top_k,
            payload.max_revision_rounds,
        )
        result = nutrition_workflow_service.run_main_flow(dict(current_user), payload)
        logger.info(
            "Nutrition recommendation completed | user_id=%s | request_id=%s | passed=%s | response_time=%ss",
            current_user["id"],
            result.get("request_id"),
            (result.get("validation") or {}).get("passed"),
            result.get("response_time_seconds"),
        )
        return success_response(data=result, message="Tạo khuyến nghị dinh dưỡng thành công.")
    except ValueError as exc:
        logger.warning(
            "Nutrition recommendation validation error | user_id=%s | error=%s",
            current_user["id"],
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Nutrition recommendation failed | user_id=%s | error=%s",
            current_user["id"],
            exc,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/recommendation-agent", response_model=BaseResponse[NutritionAgentRecommendationResponse])
async def generate_nutrition_recommendation_agent(
    payload: NutritionAgentRecommendationRequest,
    current_user=Depends(PermissionChecker("chat.use")),
):
    if not settings.NUTRITION_AGENT_ENABLED:
        raise HTTPException(status_code=404, detail="Nutrition LangGraph agent is disabled.")
    try:
        result = nutrition_agent_service.run(dict(current_user), payload)
        logger.info(
            "Nutrition recommendation agent completed | user_id=%s | session_id=%s | status=%s | passed=%s",
            current_user["id"],
            result.get("session_id"),
            result.get("status"),
            result.get("validation_passed"),
        )
        return success_response(data=result, message="Tạo khuyến nghị dinh dưỡng qua LangGraph orchestration thành công.")
    except ValueError as exc:
        logger.warning(
            "Nutrition recommendation agent validation error | user_id=%s | error=%s",
            current_user["id"],
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Nutrition recommendation agent failed | user_id=%s | error=%s",
            current_user["id"],
            exc,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/workflows/{request_id}", response_model=BaseResponse[WorkflowStateResponse])
async def get_workflow_state(
    request_id: str,
    current_user=Depends(PermissionChecker("chat.use")),
):
    state = redis_state_service.get_workflow_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạng thái workflow trong Redis.")
    response_payload = {
        "request_id": request_id,
        "status": state.get("status", "unknown"),
        "payload": state,
    }
    return success_response(data=response_payload, message="Lấy trạng thái workflow thành công.")


@router.post("/evaluate", response_model=BaseResponse[NutritionEvaluationResponse])
async def evaluate_nutrition_variants(
    payload: NutritionRecommendationRequest,
    current_user=Depends(PermissionChecker("chat.use")),
):
    try:
        result = nutrition_evaluation_service.evaluate(dict(current_user), payload)
        return success_response(data=result, message="Đánh giá phương án dinh dưỡng thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
