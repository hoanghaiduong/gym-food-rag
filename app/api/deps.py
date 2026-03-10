import os
from typing import Generator, Set

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


db_url = settings.database_url
engine = create_engine(
    db_url,
    connect_args={"connect_timeout": 1},
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
security = HTTPBearer()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    token_obj: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token khong hop le hoac da het han.",
    )

    try:
        token = token_obj.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if username is None or token_type != "access":
            raise auth_error
    except JWTError:
        raise auth_error

    result = db.execute(
        text("SELECT * FROM users WHERE username = :u"),
        {"u": username},
    ).mappings().fetchone()

    if result is None:
        raise auth_error
    if not result["is_active"]:
        raise HTTPException(403, "Tai khoan bi khoa.")

    return result


def get_user_permissions(user_id: int, db: Session) -> Set[str]:
    query = text(
        """
        SELECT DISTINCT p.slug
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN user_roles ur ON rp.role_id = ur.role_id
        WHERE ur.user_id = :uid
        """
    )
    result = db.execute(query, {"uid": user_id}).fetchall()
    return {row[0] for row in result}


class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(self, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
        perms = get_user_permissions(current_user["id"], db)
        if self.required_permission not in perms:
            if "system.config" in perms:
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ban thieu quyen: '{self.required_permission}'",
            )
        return current_user


async def get_current_admin(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    perms = get_user_permissions(current_user["id"], db)
    if "system.config" not in perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yeu cau quyen Quan tri vien (Admin).",
        )
    return current_user


async def verify_admin(x_admin_key: str = Header(..., description="Admin Setup Key")):
    current_key = os.getenv("ADMIN_SECRET_KEY", settings.ADMIN_SECRET_KEY)
    if x_admin_key != current_key:
        raise HTTPException(403, "Sai Setup Key.")
    return True
