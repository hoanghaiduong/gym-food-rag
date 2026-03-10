from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

T = TypeVar("T")

class MetaData(BaseModel):
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

def success_response(
    data: Any = None, 
    message: str = "Success", 
    code: int = 200, 
    meta: Any = None
):
    """
    Return a standardized success response.
    """
    return {
        "status": "success",
        "code": code,
        "message": message,
        "data": jsonable_encoder(data),
        "meta": jsonable_encoder(meta) if meta else None
    }

def error_response(
    message: str, 
    code: int = 400, 
    detail: Any = None
):
    """
    Return a standardized error response.
    """
    return {
        "status": "error",
        "code": code,
        "message": message,
        "detail": jsonable_encoder(detail)
    }
