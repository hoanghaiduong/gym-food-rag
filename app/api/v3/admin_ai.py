from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import PermissionChecker, get_db
from app.core.response import BaseResponse, success_response
from app.schemas.ai_control import (
    AIConfigResponse,
    AIConfigUpdate,
    AIControlVersionCreate,
    AIControlVersionResponse,
    AIFeedbackResponse,
    AITrainingDataExportResponse,
)
from app.services.ai_control_service import ai_control_service
from app.services.ai_runtime_config import ai_runtime_config_service


router = APIRouter()


@router.get("/config", response_model=BaseResponse[AIConfigResponse])
async def get_ai_config(
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    _ = current_user
    versions = ai_control_service.list_versions(db, kind="config")
    return success_response(
        data={"active_config": ai_control_service.active_config(db), "versions": versions},
        message="Lấy cấu hình AI thành công.",
    )


@router.put("/config", response_model=BaseResponse[AIControlVersionResponse])
async def update_ai_config(
    payload: AIConfigUpdate,
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    try:
        data = ai_control_service.upsert_config(db, payload=payload, actor_user_id=current_user["id"])
        ai_runtime_config_service.invalidate()
        return success_response(data=data, message="Cập nhật cấu hình AI runtime thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/prompts", response_model=BaseResponse[list[AIControlVersionResponse]])
async def list_ai_prompts(
    module: Optional[str] = Query(default=None),
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    _ = current_user
    return success_response(data=ai_control_service.list_versions(db, kind="prompt", module=module))


@router.post("/prompts", response_model=BaseResponse[AIControlVersionResponse])
async def create_ai_prompt(
    payload: AIControlVersionCreate,
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    data = ai_control_service.create_version(db, kind="prompt", payload=payload, actor_user_id=current_user["id"])
    return success_response(data=data, message="Tạo draft prompt AI thành công.")


@router.post("/prompts/{version_id}/validate", response_model=BaseResponse[AIControlVersionResponse])
async def validate_ai_prompt(
    version_id: int,
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    data = ai_control_service.validate_version(db, version_id=version_id, actor_user_id=current_user["id"])
    return success_response(data=data, message="Validate prompt AI thành công.")


@router.post("/prompts/{version_id}/publish", response_model=BaseResponse[AIControlVersionResponse])
async def publish_ai_prompt(
    version_id: int,
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    try:
        data = ai_control_service.publish_version(db, version_id=version_id, actor_user_id=current_user["id"])
        ai_runtime_config_service.invalidate()
        return success_response(data=data, message="Publish prompt AI thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/rules", response_model=BaseResponse[list[AIControlVersionResponse]])
async def list_ai_rules(
    module: Optional[str] = Query(default=None),
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    _ = current_user
    return success_response(data=ai_control_service.list_versions(db, kind="rule", module=module))


@router.post("/rules", response_model=BaseResponse[AIControlVersionResponse])
async def create_ai_rule(
    payload: AIControlVersionCreate,
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    data = ai_control_service.create_version(db, kind="rule", payload=payload, actor_user_id=current_user["id"])
    return success_response(data=data, message="Tạo draft rule AI thành công.")


@router.post("/rules/{version_id}/validate", response_model=BaseResponse[AIControlVersionResponse])
async def validate_ai_rule(
    version_id: int,
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    data = ai_control_service.validate_version(db, version_id=version_id, actor_user_id=current_user["id"])
    return success_response(data=data, message="Validate rule AI thành công.")


@router.post("/rules/{version_id}/publish", response_model=BaseResponse[AIControlVersionResponse])
async def publish_ai_rule(
    version_id: int,
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    try:
        data = ai_control_service.publish_version(db, version_id=version_id, actor_user_id=current_user["id"])
        ai_runtime_config_service.invalidate()
        return success_response(data=data, message="Publish rule AI thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback", response_model=BaseResponse[list[AIFeedbackResponse]])
async def list_ai_feedback(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    _ = current_user
    data = ai_control_service.list_feedback(db, date_from=date_from, date_to=date_to)
    return success_response(data=data, message="Lấy feedback AI thành công.")


@router.get("/training-data/export", response_model=BaseResponse[AITrainingDataExportResponse])
async def export_ai_training_data(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user=Depends(PermissionChecker("system.config")),
    db: Session = Depends(get_db),
):
    _ = current_user
    items = ai_control_service.list_feedback(db, date_from=date_from, date_to=date_to)
    data = {"generated_at": datetime.now(timezone.utc), "item_count": len(items), "items": items}
    return success_response(data=data, message="Export training data AI thành công.")
