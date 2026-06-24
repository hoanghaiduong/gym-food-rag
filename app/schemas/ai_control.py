from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


AIControlKind = Literal["config", "prompt", "rule"]
AIControlStatus = Literal["draft", "validated", "published", "archived"]


class AIControlVersionCreate(BaseModel):
    module: str = Field(min_length=1, max_length=100)
    payload: Dict[str, Any]


class AIConfigUpdate(BaseModel):
    module: str = Field(default="llm_runtime", min_length=1, max_length=100)
    payload: Dict[str, Any]


class AIControlValidationReport(BaseModel):
    passed: bool
    issues: List[str] = Field(default_factory=list)


class AIControlVersionResponse(BaseModel):
    id: int
    kind: str
    module: str
    version: str
    payload: Dict[str, Any]
    status: str
    validation_report: Optional[AIControlValidationReport] = None
    created_by: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AIConfigResponse(BaseModel):
    active_config: Dict[str, Any]
    versions: List[AIControlVersionResponse]


class AIFeedbackCreate(BaseModel):
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    issue_tags: List[str] = Field(default_factory=list)
    correction_text: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class AIFeedbackResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    rating: Optional[int] = None
    issue_tags: List[str] = Field(default_factory=list)
    correction_text: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class AITrainingDataExportResponse(BaseModel):
    generated_at: datetime
    item_count: int
    items: List[AIFeedbackResponse]
