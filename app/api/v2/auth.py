from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from jose import jwt, JWTError

from app.api.deps import get_db, get_current_user
from app.core.security import create_reset_token, verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.config import settings
from app.schemas import PasswordResetConfirm, PasswordResetRequest, Token, UserCreate, UserLogin, UserResponse, RefreshTokenRequest

router = APIRouter()

# 1. ÄÄ‚NG KÃ (Public - Ai cÅ©ng táº¡o Ä‘Æ°á»£c, máº·c Ä‘á»‹nh lÃ  User)
@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check trÃ¹ng username
    check = db.execute(text("SELECT 1 FROM users WHERE username=:u OR email=:e"), 
                       {"u": user_in.username, "e": user_in.email}).fetchone()
    if check:
        raise HTTPException(400, "Username hoáº·c Email Ä‘Ã£ tá»“n táº¡i.")
    raw_password = user_in.password
    if len(raw_password.encode('utf-8')) > 72:
        raw_password = raw_password[:72]
    hashed_pw = get_password_hash(raw_password)
    role = "user" # Máº·c Ä‘á»‹nh

    sql = text("""
        INSERT INTO users (username, email, password_hash, full_name, role, is_active)
        VALUES (:u, :e, :p, :f, :r, :a) 
        RETURNING id, username, email, role, is_active
    """)
    
    # Thá»±c thi vÃ  láº¥y káº¿t quáº£ tráº£ vá»
    new_user = db.execute(sql, {
        "u": user_in.username, 
        "e": user_in.email, 
        "p": hashed_pw, 
        "f": user_in.full_name,
        "r": role, 
        "a": True
    }).fetchone()
    
    db.commit()
    return new_user

# 2. ÄÄ‚NG NHáº¬P (Tráº£ vá» Access + Refresh Token)
# 2. ÄÄ‚NG NHáº¬P (Há»— trá»£ Username hoáº·c Email)
@router.post("/login", response_model=Token)
async def login(form_data: UserLogin = Body(), db: Session = Depends(get_db)):
    try:
        # [Sá»¬A Äá»”I] TÃ¬m user theo username HOáº¶C email
        # form_data.username chá»©a giÃ¡ trá»‹ ngÆ°á»i dÃ¹ng nháº­p (cÃ³ thá»ƒ lÃ  tÃªn hoáº·c email)
        user = db.execute(
            text("SELECT * FROM users WHERE username = :u OR email = :u"), 
            {"u": form_data.username}
        ).fetchone()
        
        # Xá»­ lÃ½ giá»›i háº¡n Ä‘á»™ dÃ i máº­t kháº©u (Bcrypt max 72 bytes)
        login_password = form_data.password
        if len(login_password.encode('utf-8')) > 72:
            login_password = login_password[:72]

        # Kiá»ƒm tra máº­t kháº©u
        if not user or not verify_password(login_password, user.password_hash):
            raise HTTPException(status_code=401, detail="Sai tÃ i khoáº£n hoáº·c máº­t kháº©u")
        
        # Kiá»ƒm tra tÃ i khoáº£n bá»‹ khÃ³a
        if not user.is_active:
            raise HTTPException(status_code=400, detail="TÃ i khoáº£n bá»‹ khÃ³a")

        # Táº¡o Token
        # LÆ°u Ã½: user.username láº¥y tá»« DB Ä‘á»ƒ Ä‘áº£m báº£o thá»‘ng nháº¥t trong Token
        access_token = create_access_token(data={"sub": user.username, "role": user.role})
        refresh_token = create_refresh_token(data={"sub": user.username})

        # LÆ°u Refresh Token vÃ o DB
        db.execute(text("UPDATE users SET refresh_token = :rt WHERE id = :id"), 
                {"rt": refresh_token, "id": user.id})
        db.commit()

        return {
            "access_token": access_token, 
            "refresh_token": refresh_token, 
            "token_type": "bearer"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        # In lá»—i ra console server Ä‘á»ƒ debug
        print(f"Login Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Lá»—i há»‡ thá»‘ng khi Ä‘Äƒng nháº­p")
# 3. LÃ€M Má»šI TOKEN (Khi Access Token háº¿t háº¡n)
@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        
        # Kiá»ƒm tra trong DB
        user = db.execute(text("SELECT * FROM users WHERE username = :u"), {"u": username}).fetchone()
        
        # Náº¿u token gá»­i lÃªn KHÃC token trong DB -> CÃ³ thá»ƒ token cÅ© Ä‘Ã£ bá»‹ thu há»“i
        if not user or user.refresh_token != request.refresh_token:
            raise HTTPException(401, "PhiÃªn Ä‘Äƒng nháº­p khÃ´ng há»£p lá»‡ (Vui lÃ²ng Ä‘Äƒng nháº­p láº¡i)")
            
        # Cáº¥p má»›i Access Token
        new_access_token = create_access_token(data={"sub": user.username, "role": user.role})
        
        return {
            "access_token": new_access_token,
            "refresh_token": request.refresh_token, # Giá»¯ nguyÃªn refresh token cÅ©
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(401, "Refresh Token háº¿t háº¡n hoáº·c khÃ´ng há»£p lá»‡")

# 4. ÄÄ‚NG XUáº¤T
@router.post("/logout")
async def logout(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    # XÃ³a refresh token trong DB -> Token cÅ© bá»‹ vÃ´ hiá»‡u hÃ³a ngay láº­p tá»©c
    db.execute(text("UPDATE users SET refresh_token = NULL WHERE id = :id"), {"id": current_user["id"]})
    db.commit()
    return {"message": "ÄÄƒng xuáº¥t thÃ nh cÃ´ng"}

# 5. Láº¤Y THÃ”NG TIN CÃ NHÃ‚N
@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user


# --- 5. YÃŠU Cáº¦U QUÃŠN Máº¬T KHáº¨U (Gá»­i Email) ---
@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """
    BÆ°á»›c 1: NgÆ°á»i dÃ¹ng gá»­i Email. Há»‡ thá»‘ng táº¡o Link reset.
    """
    # 1. TÃ¬m user qua email
    user = db.execute(text("SELECT * FROM users WHERE email = :e"), {"e": request.email}).fetchone()
    
    # Báº£o máº­t: DÃ¹ email khÃ´ng tá»“n táº¡i, váº«n bÃ¡o thÃ nh cÃ´ng Ä‘á»ƒ trÃ¡nh hacker dÃ² email
    if not user:
        return {"message": "Náº¿u email tá»“n táº¡i trong há»‡ thá»‘ng, chÃºng tÃ´i sáº½ gá»­i hÆ°á»›ng dáº«n reset."}

    # 2. Táº¡o Token Reset (chá»‰ sá»‘ng 15 phÃºt)
    reset_token = create_reset_token(user.email)
    
    # 3. Giáº£ láº­p gá»­i Email (In ra console)
    # Trong thá»±c táº¿, báº¡n sáº½ dÃ¹ng thÆ° viá»‡n gá»­i email tháº­t á»Ÿ Ä‘Ã¢y
    def send_mock_email(email: str, token: str):
        print("="*50)
        print(f"ðŸ“§ [MOCK EMAIL] Gá»­i tá»›i: {email}")
        print(f"ðŸ”— Link Reset: http://localhost:5173/reset-password?token={token}")
        print("="*50)

    background_tasks.add_task(send_mock_email, request.email, reset_token)
    
    return {"message": "ÄÃ£ gá»­i hÆ°á»›ng dáº«n reset máº­t kháº©u vÃ o email cá»§a báº¡n."}

# --- 6. THá»°C HIá»†N Äá»”I Máº¬T KHáº¨U Má»šI ---
@router.post("/reset-password")
async def reset_password_confirm(
    data: PasswordResetConfirm, 
    db: Session = Depends(get_db)
):
    """
    BÆ°á»›c 2: NgÆ°á»i dÃ¹ng gá»­i Token + Máº­t kháº©u má»›i Ä‘á»ƒ cáº­p nháº­t.
    """
    try:
        # 1. Giáº£i mÃ£ Token
        payload = jwt.decode(data.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")

        if email is None or token_type != "reset":
            raise HTTPException(status_code=400, detail="Token khÃ´ng há»£p lá»‡.")
            
    except JWTError:
        raise HTTPException(status_code=400, detail="Token Ä‘Ã£ háº¿t háº¡n hoáº·c bá»‹ lá»—i.")

    # 2. Kiá»ƒm tra user tá»“n táº¡i
    user = db.execute(text("SELECT * FROM users WHERE email = :e"), {"e": email}).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="NgÆ°á»i dÃ¹ng khÃ´ng tá»“n táº¡i.")

    # 3. Hash máº­t kháº©u má»›i
    # (Nhá»› xá»­ lÃ½ vá»¥ 72 bytes náº¿u cáº§n thiáº¿t nhÆ° á»Ÿ trÃªn)
    new_password_hash = get_password_hash(data.new_password)

    # 4. Cáº­p nháº­t vÃ o DB
    # Äá»“ng thá»i xÃ³a refresh_token cÅ© Ä‘á»ƒ báº¯t Ä‘Äƒng nháº­p láº¡i á»Ÿ má»i nÆ¡i
    db.execute(
        text("UPDATE users SET password_hash = :p, refresh_token = NULL WHERE email = :e"),
        {"p": new_password_hash, "e": email}
    )
    db.commit()

    return {"message": "Äá»•i máº­t kháº©u thÃ nh cÃ´ng. Vui lÃ²ng Ä‘Äƒng nháº­p láº¡i."}
