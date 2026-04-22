# Docker Compose

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `docker-compose.yml`, `Dockerfile`

## Tong quan

He thong su dung **Docker Compose** de quan ly 5 infrastructure services. FastAPI backend chay ngoai Docker (de debug) hoac trong Docker (production).

---

## Docker Compose Services

### Qdrant (Vector Database)

```yaml
qdrant:
  image: qdrant/qdrant:latest
  container_name: gym_qdrant
  ports:
    - "6333:6333"
  volumes:
    - ./storage/qdrant:/qdrant/storage
  restart: always
```

| Thuoc tinh | Gia tri |
|-----------|---------|
| Dashboard | http://localhost:6333/dashboard |
| API | http://localhost:6333 |
| Storage | `./storage/qdrant/` (git-ignored) |

### Ollama (LLM)

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: gym_ollama
  ports:
    - "11434:11434"
  volumes:
    - ./storage/ollama:/root/.ollama
  restart: always
```

| Thuoc tinh | Gia tri |
|-----------|---------|
| API | http://localhost:11434 |
| Models | `./storage/ollama/` |
| Tai model | `docker exec -it gym_ollama ollama pull qwen2.5:3b` |

> **GPU Support:** Them `deploy.resources.reservations.devices` cho NVIDIA GPU acceleration.

### PostgreSQL 15

```yaml
postgres:
  image: postgres:15-alpine
  container_name: gym_postgres
  ports:
    - "5432:5432"
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-admin}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-admin}
    POSTGRES_DB: ${POSTGRES_DB:-gym_food_db}
  volumes:
    - ./storage/postgres:/var/lib/postgresql/data
  restart: always
```

| Thuoc tinh | Gia tri |
|-----------|---------|
| Connection | `postgresql://admin:admin@localhost:5432/gym_food_db` |
| Storage | `./storage/postgres/` |

### pgAdmin 4

```yaml
pgadmin:
  image: dpage/pgadmin4
  container_name: gym_pgadmin
  ports:
    - "5050:80"
  environment:
    PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:-admin@gymfood.com}
    PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD:-admin}
  depends_on:
    - postgres
  restart: always
```

| Thuoc tinh | Gia tri |
|-----------|---------|
| Web UI | http://localhost:5050 |
| Login | admin@gymfood.com / admin |

### Redis Stack

```yaml
redis:
  image: redis/redis-stack:latest
  container_name: gym_redis
  ports:
    - "6379:6379"    # Redis CLI
    - "8001:8001"    # Redis Insight
  volumes:
    - ./storage/redis:/data
  restart: always
```

| Thuoc tinh | Gia tri |
|-----------|---------|
| CLI | `redis-cli -h localhost -p 6379` |
| Redis Insight | http://localhost:8001 |
| Storage | `./storage/redis/` |

---

## Backend (Dockerfile)

Backend co Dockerfile san nhung **binh thuong chay ngoai Docker**:

```dockerfile
FROM python:3.10-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y build-essential
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

De chay trong Docker, uncomment block `backend:` trong `docker-compose.yml`:

```yaml
backend:
  build: .
  container_name: gym_backend
  ports:
    - "7563:8000"
  volumes:
    - .:/app
    - ./hf_cache:/root/.cache/huggingface
  env_file:
    - .env
  depends_on:
    - qdrant
    - ollama
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Lenh Thuong dung

```powershell
# Khoi dong tat ca services
docker-compose up -d

# Xem trang thai
docker-compose ps

# Xem logs
docker-compose logs -f qdrant
docker-compose logs -f ollama

# Dung tat ca
docker-compose down

# Dung va xoa data (CAUTION!)
docker-compose down -v

# Restart 1 service
docker-compose restart redis
```

---

## Volumes & Data Persistence

| Service | Volume path | Git-ignored |
|---------|------------|-------------|
| Qdrant | `./storage/qdrant/` | Co |
| Ollama | `./storage/ollama/` | Co |
| PostgreSQL | `./storage/postgres/` | Co |
| Redis | `./storage/redis/` | Co |
| HF Cache | `./hf_cache/` | Co |

> **Luu y:** `docker-compose down -v` se **XOA** toan bo data. Chi dung khi muon reset hoan toan.

---

## Port Map

| Port | Service | Muc dich |
|------|---------|----------|
| 8000 | FastAPI | API server |
| 5432 | PostgreSQL | Database |
| 5050 | pgAdmin | DB admin UI |
| 6333 | Qdrant | Vector DB + Dashboard |
| 6379 | Redis | Cache & state |
| 8001 | Redis Insight | Redis admin UI |
| 11434 | Ollama | LLM API |

---

## Lien ket

- [Huong dan cai dat](../getting-started/installation.md)
- [Production Deployment](production.md)
- [Cau hinh](../getting-started/configuration.md)
