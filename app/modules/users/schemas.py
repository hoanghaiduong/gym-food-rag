from typing import List
from app.schemas.users import UserResponse, UserRoleUpdate

class UserWithRoles(UserResponse):
    roles: List[str]
