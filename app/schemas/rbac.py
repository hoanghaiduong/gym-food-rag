from pydantic import BaseModel
from typing import List, Optional
# ==========================================
# 1. PERMISSION SCHEMAS
# ==========================================
class PermissionBase(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None

# Dùng để tạo mới (giống Base)
class PermissionCreate(PermissionBase):
    pass

# Dùng để response về Client (có thêm ID)
class PermissionResponse(PermissionBase):
    id: int

    class Config:
        from_attributes = True  # Pydantic v2 (Dùng orm_mode = True nếu dùng v1)
        
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
    name: Optional[str] = None
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