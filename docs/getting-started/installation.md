# Huong dan Cai dat

> Cap nhat lan cuoi: 2026-04-06  
> Source: `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `.env.example`

## Yeu cau He thong

| Thanh phan | Yeu cau toi thieu | Khuyen nghi |
|-----------|-------------------|-------------|
| Python | 3.10+ | 3.11+ |
| Docker | 20.10+ | Latest |
| Docker Compose | v2.0+ | Latest |
| RAM | 8 GB | 16 GB (cho Ollama + BGE-M3) |
| Disk | 10 GB | 20 GB (bao gom model AI) |
| GPU | Khong bat buoc | NVIDIA GPU (tang toc Ollama & embedding) |

---

## Buoc 1: Clone Repository

```bash
git clone <repo-url>
cd gym-food-rag
```

---

## Buoc 2: Tao Virtual Environment

```powershell
# Windows
python -m venv myenv
.\myenv\Scripts\Activate.ps1

# Linux/Mac
python3 -m venv myenv
source myenv/bin/activate
```

---

## Buoc 3: Cai dat Dependencies

```bash
pip install -r requirements.txt
```

**Luu y:** Mot so package can build tools:
- `FlagEmbedding`: can `build-essential` (Linux) hoac Visual C++ Build Tools (Windows)
- `psycopg[binary]`: can PostgreSQL client libraries
- `sentence-transformers`: se tu dong download model BGE-M3 (~2.3 GB) lan dau chay

---

## Buoc 4: Cau hinh Environment

```powershell
# Copy file mau
cp .env.example .env
```

Sua cac gia tri quan trong trong `.env`:

```env
# BAT BUOC thay doi
SECRET_KEY="your-random-secret-key-here"
ADMIN_SECRET_KEY="your-admin-secret-key"

# Chon LLM backend (ollama hoac gemini)
LLM_BACKEND="ollama"

# Neu dung Gemini, can API key
GOOGLE_API_KEY="your-google-api-key"

# Database (giu mac dinh neu dung Docker)
POSTGRES_USER="admin"
POSTGRES_PASSWORD="admin"
POSTGRES_DB="gym_food_db"
```

> Chi tiet cau hinh: [Tham chieu cau hinh](configuration.md)

---

## Buoc 5: Khoi dong Infrastructure (Docker)

```powershell
docker-compose up -d
```

Cac service se khoi dong:

| Service | Container | Port | Kiem tra |
|---------|-----------|------|----------|
| Qdrant | `gym_qdrant` | 6333 | http://localhost:6333/dashboard |
| PostgreSQL | `gym_postgres` | 5432 | `psql -h localhost -U admin -d gym_food_db` |
| Redis | `gym_redis` | 6379 | `redis-cli ping` |
| pgAdmin | `gym_pgadmin` | 5050 | http://localhost:5050 |
| Ollama | `gym_ollama` | 11434 | http://localhost:11434 |

Kiem tra tat ca da chay:

```powershell
docker-compose ps
```

---

## Buoc 6: Tai Model Ollama

```powershell
docker exec -it gym_ollama ollama pull qwen2.5:3b
```

Kiem tra model:

```powershell
docker exec -it gym_ollama ollama list
```

---

## Buoc 7: Khoi tao Database & Seed Data

Truy cap API setup wizard:

```powershell
# Chay server truoc
python start.py
```

Sau do goi endpoint setup:

```bash
# Tao tables va seed data (roles, permissions, admin user)
curl -X POST http://localhost:8000/api/v2/setup/init \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-admin-secret-key"
```

---

## Buoc 8: Nhap Du lieu Dinh duong

```powershell
# Build knowledge base tu CSV goc
python -m scripts.build_nutrition_master

# Ingest vao Qdrant (hybrid dense+sparse)
python -m scripts.ingest_v3
```

> Chi tiet: [Data Pipeline](../data-pipeline/overview.md)

---

## Buoc 9: Chay API Server

```powershell
# Cach 1: Dung start.py
python start.py

# Cach 2: Dung PowerShell script (co reload)
.\run_server.ps1

# Cach 3: Truc tiep voi uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Buoc 10: Xac nhan Hoat dong

```bash
# Health check
curl http://localhost:8000/

# Ket qua mong doi:
# {"status":"success","code":200,"message":"API is running!","data":{"service":"Gym Food RAG"},"meta":null}
```

Truy cap Swagger UI: **http://localhost:8000/docs**

---

## Xu ly Loi Thuong gap

### Qdrant khong ket noi duoc
```
Connection refused: localhost:6333
```
**Giai phap:** Kiem tra container dang chay: `docker logs gym_qdrant`

### Ollama timeout
```
OLLAMA_REQUEST_TIMEOUT_SECONDS=600
```
**Giai phap:** Tang timeout trong `.env`, hoac chuyen sang `LLM_BACKEND="gemini"`

### BGE-M3 download cham
Lan dau chay, model BGE-M3 (~2.3 GB) se duoc download tu HuggingFace. Dam bao mang on dinh.

### PostgreSQL permission denied
**Giai phap:** Xoa volume va tao lai: `docker-compose down -v && docker-compose up -d postgres`

### Import errors
```powershell
python -m scripts.debug_import
```

---

## Lien ket

- [Cau hinh chi tiet](configuration.md)
- [Chay nhanh 5 phut](quickstart.md)
- [Docker Compose](../deployment/docker.md)
