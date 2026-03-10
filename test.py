import requests
import time

# Cấu hình
URL_OLLAMA = "http://127.0.0.1:11434"  # Dùng IP số thay vì localhost cho chắc chắn
MODEL_NAME = "qwen2.5:3b"              # Tên model bạn đã có trong list

# --- BƯỚC 1: KIỂM TRA KẾT NỐI MẠNG (PING) ---
print(f"1. Đang kiểm tra kết nối tới {URL_OLLAMA}...")
try:
    # Gọi API tags (nhẹ) để xem server sống hay chết
    check = requests.get(f"{URL_OLLAMA}/api/tags", timeout=5)
    if check.status_code == 200:
        print("✅ Kết nối mạng THÀNH CÔNG! Server Ollama đang hoạt động.")
    else:
        print(f"❌ Kết nối được nhưng server trả về lỗi: {check.status_code}")
except Exception as e:
    print(f"❌ KHÔNG THỂ KẾT NỐI: {e}")
    print("👉 Hãy kiểm tra lại xem Docker Container có đang chạy không?")
    exit() # Dừng chương trình nếu mạng hỏng

# --- BƯỚC 2: GỬI YÊU CẦU XỬ LÝ (NẶNG) ---
print("\n2. Đang gửi câu hỏi cho AI... (Vui lòng đợi 1-2 phút)...")

context = """
Cách tính macro dinh dưoỡng cho một người trưởng thành như thế nào
"""

prompt = f"""
[CONTEXT]
{context}

Trả lời bằng tiếng Việt.
"""

start_time = time.time()
try:
    res = requests.post(
        f"{URL_OLLAMA}/api/generate",
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_ctx": 2048
            }
        },
        timeout=300 # Đặt 300 giây (5 phút) là BẮT BUỘC cho máy cấu hình tầm trung
    )
    
    res.raise_for_status()
    data = res.json()
    
    end_time = time.time()
    print(f"\n✅ XONG! (Mất {round(end_time - start_time, 2)} giây)")
    print("--- KẾT QUẢ ---")
    print(data["response"])

except requests.exceptions.ReadTimeout:
    print("\n⚠️ LỖI TIMEOUT: AI chạy quá lâu > 300 giây.")
    print("Gợi ý: Card 1660 Ti của bạn có thể đang bị quá tải hoặc model chưa load xong.")