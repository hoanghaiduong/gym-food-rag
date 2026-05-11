from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import insert, select, update, or_
from datetime import timedelta
from typing import List, Optional

# Import Dependencies & Security
from app.api.deps import get_db, get_current_user, get_user_permissions
from app.core.security import (
    create_access_token, 
    create_refresh_token, 
    verify_password,
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# Import Tables & Schemas
from app.db.tables import users, roles, user_roles
from app.schemas import (
    OtpRequest,
    OtpRequestResponse,
    OtpVerifyRequest,
    OtpVerifyResponse,
    PasswordResetWithOtpRequest,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from pydantic import BaseModel

# Import Global Response Helper (Äáº£m báº£o báº¡n Ä‘Ã£ táº¡o file app/core/response.py)
from app.core.response import BaseResponse, success_response
from app.services.auth import otp_service
from app.services.nutrition_workflow_service import nutrition_workflow_service
from app.services.user_profile_contract import build_current_user_contract

router = APIRouter()

# ==========================================
# DATA SCHEMAS (Cáº¥u trÃºc dá»¯ liá»‡u bÃªn trong 'data')
# ==========================================
class LoginData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    permissions: List[str]

class UserData(UserResponse):
    permissions: List[str]
    goal_raw_semantic: Optional[str] = None
    goal_normalized_internal: Optional[str] = None
    planning_strategy: Optional[str] = None
    is_profile_completed: bool

# ==========================================
# 1. REGISTER (ÄÄ‚NG KÃ)
# ==========================================
@router.post("/register", response_model=BaseResponse[UserResponse])
async def register_v3(user_data: UserCreate, db: Session = Depends(get_db)):
    # 1. Check user tá»“n táº¡i
    existing_user = db.execute(
        select(users).where((users.c.email == user_data.email) | (users.c.username == user_data.username))
    ).fetchone()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Email hoặc Username đã tồn tại")

    # 2. Táº¡o User (Hash pass & Insert)
    hashed_password = get_password_hash(user_data.password)
    
    try:
        stmt = insert(users).values(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            full_name=user_data.full_name,
            phone=user_data.phone,
            referral_code=user_data.referral_code,
            is_active=True
           
        ).returning(users)
        
        new_user = db.execute(stmt).mappings().fetchone()
        
        # 3. GÃ¡n Role máº·c Ä‘á»‹nh 'user'
        default_role_id = db.execute(
            select(roles.c.id).where(roles.c.name == 'user') 
        ).scalar_one_or_none()

        if default_role_id:
            db.execute(
                insert(user_roles).values(user_id=new_user.id, role_id=default_role_id)
            )
        else:
            # Náº¿u chÆ°a cÃ³ role 'user', táº¡o táº¡m thá»i hoáº·c log warning
            print("WARNING: Role 'user' chÆ°a tá»“n táº¡i. User má»›i sáº½ khÃ´ng cÃ³ quyá»n.")

        db.commit()
        
        # Tráº£ vá» Global Response
        return success_response(data=new_user, message="Đăng ký thành công")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lá»—i há»‡ thá»‘ng: {str(e)}")

# ==========================================
# 2. LOGIN (ÄÄ‚NG NHáº¬P)
# ==========================================
@router.post("/login", response_model=BaseResponse[LoginData])
async def login_v3(user_data: UserLogin, db: Session = Depends(get_db)):
    # 1. TÃ¬m user báº±ng Username HOáº¶C Email
    # user_data.username lÃ  dá»¯ liá»‡u ngÆ°á»i dÃ¹ng nháº­p vÃ o (cÃ³ thá»ƒ lÃ  tÃªn hoáº·c email)
    user = db.execute(
        select(users).where(
            or_(
                users.c.username == user_data.username, # So khá»›p vá»›i cá»™t username
                users.c.email == user_data.username     # So khá»›p vá»›i cá»™t email
            )
        )
    ).mappings().fetchone()

    # --- Pháº§n cÃ²n láº¡i giá»¯ nguyÃªn ---
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Táº¡o Tokens
    # LÆ°u Ã½: DÃ¹ Ä‘Äƒng nháº­p báº±ng email, token váº«n nÃªn lÆ°u 'sub' lÃ  username gá»‘c trong DB Ä‘á»ƒ thá»‘ng nháº¥t
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "id": user.id}, 
        expires_delta=access_token_expires
    )
    
    # [NEW] Táº¡o Opaque Refresh Token
    refresh_token, refresh_expires_at = create_refresh_token()

    # 3. Update Refresh Token vÃ o DB (KÃ¨m Expiry)
    db.execute(
        update(users).where(users.c.id == user.id).values(
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_expires_at
        )
    )
    db.commit()

    # 4. Láº¥y Permissions
    perms = get_user_permissions(user.id, db)

    # 5. Tráº£ vá» káº¿t quáº£ chuáº©n
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "permissions": list(perms)
    }
    return success_response(data=data, message="Đăng nhập thành công")


@router.post("/otp/request", response_model=BaseResponse[OtpRequestResponse])
async def request_otp_v3(payload: OtpRequest, db: Session = Depends(get_db)):
    try:
        data = otp_service.request_otp(
            db,
            target=payload.target,
            channel=payload.channel,
            purpose=payload.purpose,
        )
        return success_response(data=data, message="Đã tạo mã OTP.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/otp/verify", response_model=BaseResponse[OtpVerifyResponse])
async def verify_otp_v3(payload: OtpVerifyRequest, db: Session = Depends(get_db)):
    try:
        data = otp_service.verify_otp(
            db,
            otp_request_id=payload.otp_request_id,
            code=payload.code,
        )
        return success_response(data=data, message="Xác thực OTP thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reset-password", response_model=BaseResponse[dict])
async def reset_password_with_otp_v3(
    payload: PasswordResetWithOtpRequest,
    db: Session = Depends(get_db),
):
    try:
        otp_service.reset_password(
            db,
            verification_token=payload.verification_token,
            new_password=payload.new_password,
        )
        return success_response(data=None, message="Đặt lại mật khẩu thành công.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
# ==========================================
# 3. GET ME (Láº¥y thÃ´ng tin báº£n thÃ¢n)
# ==========================================
@router.get("/me", response_model=BaseResponse[UserData])
async def read_users_me_v3(
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Tráº£ vá» thÃ´ng tin user hiá»‡n táº¡i + danh sÃ¡ch quyá»n háº¡n
    """
    perms = get_user_permissions(current_user["id"], db)
    current_user_dict = dict(current_user)
    nutrition_profile = nutrition_workflow_service.build_profile(current_user_dict)
    user_dict = build_current_user_contract(
        current_user_dict,
        permissions=perms,
        nutrition_profile=nutrition_profile,
    )
    
    return success_response(data=user_dict, message="Lấy thông tin thành công")

# ==========================================
# 4. REFRESH TOKEN
# ==========================================
# ==========================================
# 4. REFRESH TOKEN
# ==========================================
@router.post("/refresh", response_model=BaseResponse[Token])
async def refresh_token_v3(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh Access Token báº±ng Opaque Refresh Token (Stateful).
    """
    token = request.refresh_token
    
    # 1. TÃ¬m User sá»Ÿ há»¯u token nÃ y
    user = db.execute(select(users).where(users.c.refresh_token == token)).mappings().fetchone()
    
    # 2. Validate
    if not user:
         raise HTTPException(status_code=401, detail="Refresh token không hợp lệ (Không tìm thấy).")
         
    # Check Expiration
    from datetime import datetime
    if not user.refresh_token_expires_at or user.refresh_token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token Ä‘Ã£ háº¿t háº¡n. Vui lÃ²ng Ä‘Äƒng nháº­p láº¡i.")

    # 3. Token Rotation (Báº£o máº­t: Äá»•i token má»›i Ä‘á»ƒ trÃ¡nh Replay Attack)
    new_refresh_token, new_expires_at = create_refresh_token()
    
    db.execute(
        update(users).where(users.c.id == user.id).values(
            refresh_token=new_refresh_token,
            refresh_token_expires_at=new_expires_at
        )
    )
    db.commit()

    # 4. Táº¡o Access Token má»›i
    access_token = create_access_token(data={"sub": user.username, "id": user.id})
    
    data = {
        "access_token": access_token,
        "refresh_token": new_refresh_token, # Tráº£ vá» token má»›i
        "token_type": "bearer"
    }
    return success_response(data=data, message="Làm mới token thành công")

# ==========================================
# 5. LOGOUT (ÄÄ‚NG XUáº¤T)
# ==========================================
@router.post("/logout", response_model=BaseResponse)
async def logout_v3(
    current_user = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    ÄÄƒng xuáº¥t ngÆ°á»i dÃ¹ng: XÃ³a Refresh Token trong Database.
    Client cÅ©ng cáº§n xÃ³a Access/Refresh Token á»Ÿ localStorage/Cookies.
    """
    try:
        # Set refresh_token = NULL cho user hiá»‡n táº¡i
        db.execute(
            update(users).where(users.c.id == current_user["id"]).values(
                refresh_token=None,
                refresh_token_expires_at=None
            )
        )
        db.commit()
        
        return success_response(data=None, message="Đăng xuất thành công")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lá»—i Ä‘Äƒng xuáº¥t: {str(e)}")
