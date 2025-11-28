from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from jose import jwt, JWTError

from app.api.deps import get_db, get_current_user
from app.core.security import create_reset_token, verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.config import settings
from app.models.schemas import PasswordResetConfirm, PasswordResetRequest, Token, UserCreate, UserLogin, UserResponse, RefreshTokenRequest

router = APIRouter()

# 1. ĐĂNG KÝ (Public - Ai cũng tạo được, mặc định là User)
@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check trùng username
    check = db.execute(text("SELECT 1 FROM users WHERE username=:u OR email=:e"), 
                       {"u": user_in.username, "e": user_in.email}).fetchone()
    if check:
        raise HTTPException(400, "Username hoặc Email đã tồn tại.")
    raw_password = user_in.password
    if len(raw_password.encode('utf-8')) > 72:
        raw_password = raw_password[:72]
    hashed_pw = get_password_hash(raw_password)
    role = "user" # Mặc định

    sql = text("""
        INSERT INTO users (username, email, password_hash, full_name, role, is_active)
        VALUES (:u, :e, :p, :f, :r, :a) 
        RETURNING id, username, email, role, is_active
    """)
    
    # Thực thi và lấy kết quả trả về
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

# 2. ĐĂNG NHẬP (Trả về Access + Refresh Token)
# 2. ĐĂNG NHẬP (Hỗ trợ Username hoặc Email)
@router.post("/login", response_model=Token)
async def login(form_data: UserLogin = Body(), db: Session = Depends(get_db)):
    try:
        # [SỬA ĐỔI] Tìm user theo username HOẶC email
        # form_data.username chứa giá trị người dùng nhập (có thể là tên hoặc email)
        user = db.execute(
            text("SELECT * FROM users WHERE username = :u OR email = :u"), 
            {"u": form_data.username}
        ).fetchone()
        
        # Xử lý giới hạn độ dài mật khẩu (Bcrypt max 72 bytes)
        login_password = form_data.password
        if len(login_password.encode('utf-8')) > 72:
            login_password = login_password[:72]

        # Kiểm tra mật khẩu
        if not user or not verify_password(login_password, user.password_hash):
            raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu")
        
        # Kiểm tra tài khoản bị khóa
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Tài khoản bị khóa")

        # Tạo Token
        # Lưu ý: user.username lấy từ DB để đảm bảo thống nhất trong Token
        access_token = create_access_token(data={"sub": user.username, "role": user.role})
        refresh_token = create_refresh_token(data={"sub": user.username})

        # Lưu Refresh Token vào DB
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
        # In lỗi ra console server để debug
        print(f"Login Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống khi đăng nhập")
# 3. LÀM MỚI TOKEN (Khi Access Token hết hạn)
@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        
        # Kiểm tra trong DB
        user = db.execute(text("SELECT * FROM users WHERE username = :u"), {"u": username}).fetchone()
        
        # Nếu token gửi lên KHÁC token trong DB -> Có thể token cũ đã bị thu hồi
        if not user or user.refresh_token != request.refresh_token:
            raise HTTPException(401, "Phiên đăng nhập không hợp lệ (Vui lòng đăng nhập lại)")
            
        # Cấp mới Access Token
        new_access_token = create_access_token(data={"sub": user.username, "role": user.role})
        
        return {
            "access_token": new_access_token,
            "refresh_token": request.refresh_token, # Giữ nguyên refresh token cũ
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(401, "Refresh Token hết hạn hoặc không hợp lệ")

# 4. ĐĂNG XUẤT
@router.post("/logout")
async def logout(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    # Xóa refresh token trong DB -> Token cũ bị vô hiệu hóa ngay lập tức
    db.execute(text("UPDATE users SET refresh_token = NULL WHERE id = :id"), {"id": current_user.id})
    db.commit()
    return {"message": "Đăng xuất thành công"}

# 5. LẤY THÔNG TIN CÁ NHÂN
@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user


# --- 5. YÊU CẦU QUÊN MẬT KHẨU (Gửi Email) ---
@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """
    Bước 1: Người dùng gửi Email. Hệ thống tạo Link reset.
    """
    # 1. Tìm user qua email
    user = db.execute(text("SELECT * FROM users WHERE email = :e"), {"e": request.email}).fetchone()
    
    # Bảo mật: Dù email không tồn tại, vẫn báo thành công để tránh hacker dò email
    if not user:
        return {"message": "Nếu email tồn tại trong hệ thống, chúng tôi sẽ gửi hướng dẫn reset."}

    # 2. Tạo Token Reset (chỉ sống 15 phút)
    reset_token = create_reset_token(user.email)
    
    # 3. Giả lập gửi Email (In ra console)
    # Trong thực tế, bạn sẽ dùng thư viện gửi email thật ở đây
    def send_mock_email(email: str, token: str):
        print("="*50)
        print(f"📧 [MOCK EMAIL] Gửi tới: {email}")
        print(f"🔗 Link Reset: http://localhost:5173/reset-password?token={token}")
        print("="*50)

    background_tasks.add_task(send_mock_email, request.email, reset_token)
    
    return {"message": "Đã gửi hướng dẫn reset mật khẩu vào email của bạn."}

# --- 6. THỰC HIỆN ĐỔI MẬT KHẨU MỚI ---
@router.post("/reset-password")
async def reset_password_confirm(
    data: PasswordResetConfirm, 
    db: Session = Depends(get_db)
):
    """
    Bước 2: Người dùng gửi Token + Mật khẩu mới để cập nhật.
    """
    try:
        # 1. Giải mã Token
        payload = jwt.decode(data.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")

        if email is None or token_type != "reset":
            raise HTTPException(status_code=400, detail="Token không hợp lệ.")
            
    except JWTError:
        raise HTTPException(status_code=400, detail="Token đã hết hạn hoặc bị lỗi.")

    # 2. Kiểm tra user tồn tại
    user = db.execute(text("SELECT * FROM users WHERE email = :e"), {"e": email}).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại.")

    # 3. Hash mật khẩu mới
    # (Nhớ xử lý vụ 72 bytes nếu cần thiết như ở trên)
    new_password_hash = get_password_hash(data.new_password)

    # 4. Cập nhật vào DB
    # Đồng thời xóa refresh_token cũ để bắt đăng nhập lại ở mọi nơi
    db.execute(
        text("UPDATE users SET password_hash = :p, refresh_token = NULL WHERE email = :e"),
        {"p": new_password_hash, "e": email}
    )
    db.commit()

    return {"message": "Đổi mật khẩu thành công. Vui lòng đăng nhập lại."}