from sqlalchemy.orm import Session
from sqlalchemy import text, insert, delete
from app.db.tables import user_roles
from typing import List, Any

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[Any]:
        return self.db.execute(text(f"SELECT * FROM users OFFSET {skip} LIMIT {limit}")).mappings().all()

    def get_total_users(self) -> int:
        return self.db.execute(text("SELECT count(*) FROM users")).scalar()

    def get_user_roles(self, user_id: int) -> List[str]:
        return self.db.execute(text("""
            SELECT r.name FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = :uid
        """), {"uid": user_id}).scalars().all()

    def clear_user_roles(self, user_id: int):
        self.db.execute(delete(user_roles).where(user_roles.c.user_id == user_id))

    def add_user_roles(self, user_id: int, role_ids: List[int]):
         if role_ids:
            values = [{"user_id": user_id, "role_id": rid} for rid in role_ids]
            self.db.execute(insert(user_roles), values)
