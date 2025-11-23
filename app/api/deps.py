import os
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

# Key mặc định khi chưa setup
DEFAULT_KEY = "gym-food-super-admin" 

def get_current_admin_key():
    # Load lại mỗi lần gọi để đảm bảo cập nhật ngay khi .env thay đổi
    return os.getenv("ADMIN_SECRET_KEY", DEFAULT_KEY)

async def verify_admin(x_admin_key: str = Header(..., description="Key bảo mật quyền Admin")):
    """
    Dependency kiểm tra quyền Admin.
    """
    current_key = get_current_admin_key()
    
    # Case 1: Nếu user nhập đúng key hiện tại -> OK
    if x_admin_key == current_key:
        return True
        
    # Case 2: Chặn truy cập
    raise HTTPException(
        status_code=403, 
        detail="❌ Sai Admin Key! Bạn không có quyền truy cập."
    )