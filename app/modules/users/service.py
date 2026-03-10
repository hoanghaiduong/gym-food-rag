from sqlalchemy.orm import Session
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserRoleUpdate

class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def get_users_with_roles(self, page: int = 1, limit: int = 20):
        skip = (page - 1) * limit
        users = self.repo.get_all_users(skip=skip, limit=limit)
        total = self.repo.get_total_users()

        result = []
        for u in users:
            role_names = self.repo.get_user_roles(u.id)
            roles_display = list(role_names)
            
            # Fallback for old role column (backward compatibility)
            # accessing 'role' from mapping if exists
            u_role = getattr(u, 'role', None) 
            # Note: since 'u' is a RowMapping (from .mappings().all()), we usually access via key or it behaves like dict.
            # But mappings() returns RowMapping, which behaves like dict.
            # Let's check safely.
            if len(roles_display) == 0:
                 # Try to get from dict-like object
                 legacy_role = u.get('role') if hasattr(u, 'get') else getattr(u, 'role', None)
                 if legacy_role:
                     roles_display.append(legacy_role)

            user_dict = dict(u)
            user_dict['roles'] = roles_display
            result.append(user_dict)
        
        return result, total

    def assign_roles(self, user_id: int, data: UserRoleUpdate):
        try:
            self.repo.clear_user_roles(user_id)
            self.repo.add_user_roles(user_id, data.role_ids)
            self.repo.db.commit()
        except Exception as e:
            self.repo.db.rollback()
            raise e
