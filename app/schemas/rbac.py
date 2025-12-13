from pydantic import BaseModel
from typing import List, Optional

class PermissionOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    class Config:
        from_attributes = True

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    permissions: List[str] = [] 

class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

class RoleResponse(RoleBase):
    id: int
    permissions: List[str] = []
    class Config:
        from_attributes = True

class AssignRoleRequest(BaseModel):
    user_id: int
    role_name: str