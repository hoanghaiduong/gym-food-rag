from typing import Any, Generic, Optional, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict


T = TypeVar("T")


class MetaData(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int
    limit: int
    total: int
    total_pages: int


class BaseResponse(BaseModel, Generic[T]):
    status: str = "success"
    code: int = 200
    message: str = "Success"
    data: Optional[T] = None
    meta: Optional[Any] = None


def _build_response(
    *,
    status: str,
    code: int,
    message: str,
    data: Any = None,
    meta: Any = None,
    detail: Any = None,
) -> dict[str, Any]:
    payload = {
        "status": status,
        "code": code,
        "message": message,
        "data": jsonable_encoder(data),
        "meta": jsonable_encoder(meta) if meta is not None else None,
    }
    if detail is not None:
        payload["detail"] = jsonable_encoder(detail)
    return payload


def success_response(
    data: Any = None,
    message: str = "Success",
    code: int = 200,
    meta: Any = None,
) -> dict[str, Any]:
    return _build_response(
        status="success",
        code=code,
        message=message,
        data=data,
        meta=meta,
    )


def created_response(
    data: Any = None,
    message: str = "Created",
    meta: Any = None,
) -> dict[str, Any]:
    return success_response(data=data, message=message, code=201, meta=meta)


def paginated_response(
    data: Any,
    *,
    page: int,
    limit: int,
    total: int,
    message: str = "Success",
    code: int = 200,
) -> dict[str, Any]:
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    meta = MetaData(page=page, limit=limit, total=total, total_pages=total_pages)
    return success_response(data=data, message=message, code=code, meta=meta.model_dump())


def error_response(
    message: str,
    code: int = 400,
    detail: Any = None,
) -> dict[str, Any]:
    return _build_response(
        status="error",
        code=code,
        message=message,
        detail=detail,
    )
