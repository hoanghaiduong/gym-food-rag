# Chay nhanh (Quickstart)

> Cap nhat lan cuoi: 2026-04-06  
> Thoi gian: ~5 phut (gia su da cai Docker)

## TL;DR

```powershell
# 1. Clone & setup
git clone <repo-url> && cd gym-food-rag
cp .env.example .env                    # Sua SECRET_KEY va ADMIN_SECRET_KEY
python -m venv myenv
.\myenv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Khoi dong infrastructure
docker-compose up -d

# 3. Tai model Ollama
docker exec -it gym_ollama ollama pull qwen2.5:3b

# 4. Chay server
python start.py
```

---

## Kiem tra Hoat dong

### Health Check

```bash
curl http://localhost:8000/
```

Ket qua:
```json
{
  "status": "success",
  "code": 200,
  "message": "API is running!",
  "data": {"service": "Gym Food RAG"},
  "meta": null
}
```

### Swagger UI

Mo trinh duyet: **http://localhost:8000/docs**

Tai day ban co the:
- Xem tat ca endpoints
- Thu nghiem API truc tiep
- Xem request/response schemas

---

## Thu API Dau tien

### 1. Tao Admin User (Setup Wizard)

```bash
curl -X POST http://localhost:8000/api/v2/setup/init \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: change-me"
```

### 2. Dang nhap

```bash
curl -X POST http://localhost:8000/api/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

Ket qua tra ve `access_token` — su dung cho cac request tiep theo.

### 3. Goi y Dinh duong

```bash
curl -X POST http://localhost:8000/api/v3/nutrition/recommendation \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "instruction": "Toi nang 70kg, cao 175cm, muon tang co, goi y thuc don 3 bua",
    "meal_count": 3,
    "top_k": 10
  }'
```

---

## Cac Cach Chay Server

| Cach | Lenh | Hot reload | Ghi chu |
|------|------|------------|---------|
| `start.py` | `python start.py` | Theo `UVICORN_RELOAD` env | Khuyen nghi cho production |
| PowerShell | `.\run_server.ps1` | Co | Khuyen nghi cho dev |
| Batch | `.\run_server.bat` | Co | Cho cmd.exe |
| Truc tiep | `uvicorn app.main:app --reload` | Co | Linh hoat nhat |

---

## Cau truc Port Services

| Service | Port | URL |
|---------|------|-----|
| FastAPI | 8000 | http://localhost:8000 |
| Swagger UI | 8000 | http://localhost:8000/docs |
| Qdrant Dashboard | 6333 | http://localhost:6333/dashboard |
| pgAdmin | 5050 | http://localhost:5050 |
| Redis Insight | 8001 | http://localhost:8001 |
| Ollama | 11434 | http://localhost:11434 |

---

## Buoc Tiep theo

1. [Nhap du lieu dinh duong](../data-pipeline/overview.md) — Neu chua co du lieu trong Qdrant
2. [Cau hinh chi tiet](configuration.md) — Tuy chinh LLM backend, retrieval params
3. [API Reference](../api/overview.md) — Xem tat ca endpoints
4. [Kien truc tong quan](../architecture/overview.md) — Hieu cach he thong hoat dong
