# app/api/v2/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from jose import jwt, JWTError

from app.api.deps import get_db, get_current_user
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    SECRET_KEY,
    ALGORITHM,
)
from app.models.schemas import Token, UserCreate, UserResponse, RefreshTokenRequest

router = APIRouter()


# 1. ĐĂNG KÝ
@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check trùng
    check = db.execute(
        text("SELECT 1 FROM users WHERE username=:u"), {"u": user_in.username}
    ).fetchone()
    if check:
        raise HTTPException(400, "Username đã tồn tại")

    hashed_pw = get_password_hash(user_in.password)
    # Mặc định user đầu tiên là user thường. Muốn là admin phải sửa trong DB hoặc logic init.
    role = "user"

    sql = text(
        """
    INSERT INTO users (username, email, password_hash, role, is_active)
    VALUES (:u, :e, :p, :r, :a) RETURNING id, username, email, role, is_active
    """
    )
    new_user = db.execute(
        sql,
        {
            "u": user_in.username,
            "e": user_in.email,
            "p": hashed_pw,
            "r": role,
            "a": True,
        },
    ).fetchone()
    db.commit()
    return new_user


# 2. ĐĂNG NHẬP
@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.execute(
        text("SELECT * FROM users WHERE username = :u"), {"u": form_data.username}
    ).fetchone()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(401, "Sai tài khoản hoặc mật khẩu")

    # Tạo cặp Token
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.username})

    # Lưu Refresh Token vào DB
    db.execute(
        text("UPDATE users SET refresh_token = :rt WHERE id = :id"),
        {"rt": refresh_token, "id": user.id},
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# 3. REFRESH TOKEN
@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        # Kiểm tra DB xem refresh token có khớp không (Chống dùng lại token cũ)
        user = db.execute(
            text("SELECT * FROM users WHERE username = :u"), {"u": username}
        ).fetchone()
        if not user or user.refresh_token != request.refresh_token:
            raise HTTPException(401, "Token không hợp lệ hoặc đã đăng xuất")

        new_access_token = create_access_token(
            data={"sub": user.username, "role": user.role}
        )
        return {
            "access_token": new_access_token,
            "refresh_token": request.refresh_token,
            "token_type": "bearer",
        }
    except JWTError:
        raise HTTPException(401, "Token hết hạn")


# 4. ĐĂNG XUẤT
@router.post("/logout")
async def logout(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        text("UPDATE users SET refresh_token = NULL WHERE id = :id"),
        {"id": current_user.id},
    )
    db.commit()
    return {"message": "Logged out"}
