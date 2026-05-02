from typing import List
from app.schemas.users import (
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserResponse,
    UserRoleUpdate,
)

class UserWithRoles(UserResponse):
    roles: List[str]


__all__ = [
    "UserPreferencesResponse",
    "UserPreferencesUpdate",
    "UserRoleUpdate",
    "UserWithRoles",
]
