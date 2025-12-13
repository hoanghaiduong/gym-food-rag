from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class AuditLogCreate(BaseModel):
    source_name: str = "Bach Hoa Xanh"
    check_date: str 
    result: str 
    proof_url: Optional[str] = None
    notes: Optional[str] = None

class BlockchainVerifyResponse(BaseModel):
    status: str 
    data: Optional[Dict[str, Any]] = None
    message: str
    timestamp: datetime = datetime.now()