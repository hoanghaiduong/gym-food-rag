# app/core/response.py
from typing import Any, Optional

def success_response(data: Any = None, message: str = "Success"):
    return {
        "status": "success",
        "code": 200,
        "message": message,
        "data": data
    }