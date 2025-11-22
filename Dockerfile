# Sử dụng Python 3.10 slim để nhẹ nhất có thể
FROM python:3.10-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Thiết lập biến môi trường để Python không tạo file .pyc và log mượt mà
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cài đặt các dependencies hệ thống (nếu cần)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Expose port 8000
EXPOSE 8000

# Lệnh chạy ứng dụng
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]