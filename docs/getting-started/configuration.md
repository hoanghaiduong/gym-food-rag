# Tham chieu Cau hinh

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/core/config.py`, `.env.example`

He thong su dung **Pydantic Settings** de load cau hinh tu file `.env`. Tat ca bien moi truong duoc dinh nghia trong class `Settings` tai `app/core/config.py`.

---

## Cach Hoat dong

```python
# app/core/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # ...

settings = Settings()
```

- Doc tu file `.env` tai root du an
- Bien moi truong he thong co uu tien cao hon `.env`
- Cac bien khong co trong `.env` se dung gia tri mac dinh

---

## Toan bo Bien Moi truong

### Application

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `PROJECT_NAME` | str | `"Gym Food RAG"` | Ten du an, hien thi tren Swagger UI |
| `API_V1_STR` | str | `"/api/v1"` | Prefix API V1 |

### Security & Authentication

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `SECRET_KEY` | str | `"gym-food-super-secret..."` | **BAT BUOC DOI** — Key ky JWT |
| `ADMIN_SECRET_KEY` | str | `"gym-food-super-admin"` | **BAT BUOC DOI** — Key bao mat cho setup wizard |
| `ALGORITHM` | str | `"HS256"` | Thuat toan JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `30` | Thoi gian het han access token (phut) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | int | `7` | Thoi gian het han refresh token (ngay) |

### LLM Backend

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `LLM_BACKEND` | str | `"ollama"` | Backend LLM: `"ollama"` hoac `"gemini"` |
| `OLLAMA_BASE_URL` | str | `"http://localhost:11434"` | URL Ollama API |
| `OLLAMA_MODEL` | str | `"qwen2.5:3b"` | Model Ollama su dung |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | int | `600` | Timeout request den Ollama (giay) |
| `GEMINI_MODEL` | str | `"gemini-2.5-flash"` | Model Google Gemini |
| `GOOGLE_API_KEY` | str | `""` | API key Google Gemini |
| `OPENAI_API_KEY` | str | `""` | API key OpenAI (du phong) |
| `OPENAI_MODEL` | str | `"gpt-3.5-turbo"` | Model OpenAI |

### Embedding

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `USE_LOCAL_EMBEDDING` | bool | `True` | `True` = dung model local, `False` = Gemini cloud |
| `LOCAL_EMBEDDING_MODEL` | str | `"BAAI/bge-m3"` | Model embedding local |
| `SPARSE_EMBEDDING_STRATEGY` | str | `"auto"` | Chien luoc sparse: `"auto"`, `"bge_m3_native"`, `"vi_lexical"` |
| `SPARSE_HASH_DIM` | int | `2000003` | Kich thuoc khong gian sparse (so nguyen to) |
| `SPARSE_USE_BIGRAMS` | bool | `True` | Bat bigrams cho sparse encoding |
| `RETRIEVAL_RERANK_MAX_PASSAGE_LENGTH` | int | `256` | Do dai toi da passage khi rerank |
| `RETRIEVAL_RERANK_WEIGHTS` | str | `"0.4,0.2,0.4"` | Trong so rerank: dense, sparse, colbert |

### Qdrant (Vector Database)

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `QDRANT_HOST` | str | `"localhost"` | Qdrant host |
| `QDRANT_PORT` | int | `6333` | Qdrant port |
| `COLLECTION_NAME` | str | `"gym_food_hybrid_v1"` | Collection mac dinh (fallback) |
| `COLLECTION_NAME_ACTIVE` | str | `""` | Alias dang active (khuyen nghi: `"gym_food_hybrid_active"`) |
| `COLLECTION_NAME_NEXT` | str | `""` | Collection moi khi reindex (de trong khi khong migration) |
| `QDRANT_SPARSE_INDEX_ON_DISK` | bool | `True` | Luu sparse index tren disk (tiet kiem RAM) |
| `RETRIEVAL_OVERFETCH_MULTIPLIER` | int | `4` | He so overfetch: fetch 4x top_k roi loc |
| `RETRIEVAL_PREFETCH_MULTIPLIER` | int | `2` | He so prefetch cho moi nhanh (dense/sparse) |
| `RETRIEVAL_ENABLE_RERANK` | bool | `True` | Bat/tat reranking |
| `RETRIEVAL_ENABLE_NATIVE_RERANK` | bool | `False` | Bat native BGE-M3 rerank (nang, can nhieu RAM) |
| `RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS` | int | `25` | Timeout native rerank |
| `RETRIEVAL_NATIVE_RERANK_MAX_DOCS` | int | `6` | So tai lieu toi da cho native rerank |
| `RETRIEVAL_NATIVE_RERANK_MAX_CHARS` | int | `512` | So ky tu toi da moi tai lieu khi rerank |
| `RETRIEVAL_RERANK_CANDIDATES` | int | `24` | So ung cu vien truoc rerank |

### PostgreSQL

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `DATABASE_URL` | str\|None | `None` | Connection string day du (uu tien neu co) |
| `POSTGRES_HOST` | str | `"localhost"` | PostgreSQL host |
| `POSTGRES_PORT` | int | `5432` | PostgreSQL port |
| `POSTGRES_USER` | str | `"admin"` | Username |
| `POSTGRES_PASSWORD` | str | `"admin"` | Password |
| `POSTGRES_DB` | str | `"gym_food_db"` | Ten database |

> **Property:** `settings.database_url` — tu dong build connection string tu cac bien tren neu `DATABASE_URL` khong duoc set.

### pgAdmin

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `PGADMIN_EMAIL` | str | `"admin@gymfood.com"` | Email dang nhap pgAdmin |
| `PGADMIN_PASSWORD` | str | `"admin"` | Password pgAdmin |

### Redis

| Bien | Kieu | Mac dinh | Mo ta |
|------|------|----------|-------|
| `REDIS_HOST` | str | `"localhost"` | Redis host |
| `REDIS_PORT` | int | `6379` | Redis port |
| `REDIS_URL` | str\|None | `None` | Redis URL day du (uu tien neu co) |
| `EXACT_CACHE_TTL_SECONDS` | int | `900` | TTL cache ket qua nutrition (15 phut) |
| `WORKFLOW_STATE_TTL_SECONDS` | int | `3600` | TTL workflow state (1 gio) |

> **Property:** `settings.redis_url` — tu dong build tu `REDIS_HOST:REDIS_PORT` neu `REDIS_URL` khong duoc set.

---

## Computed Properties

`Settings` class co cac property duoc tinh tu cac bien khac:

| Property | Logic | Muc dich |
|----------|-------|----------|
| `database_url` | `DATABASE_URL` hoac build tu `POSTGRES_*` | Connection string PostgreSQL |
| `redis_url` | `REDIS_URL` hoac build tu `REDIS_HOST:PORT` | Connection string Redis |
| `serving_collection_name` | `COLLECTION_NAME_ACTIVE` hoac `COLLECTION_NAME` | Collection Qdrant dang phuc vu |
| `reindex_target_collection_name` | `COLLECTION_NAME_NEXT` hoac `COLLECTION_NAME` | Collection dich khi reindex |
| `alias_mode_enabled` | `bool(COLLECTION_NAME_ACTIVE)` | Co dang dung alias mode khong |

---

## Cau hinh Khuyen nghi theo Moi truong

### Development (Local)

```env
LLM_BACKEND="ollama"
OLLAMA_BASE_URL="http://localhost:11434"
RETRIEVAL_ENABLE_NATIVE_RERANK=false
COLLECTION_NAME="gym_food_hybrid_v1"
COLLECTION_NAME_ACTIVE=""
```

### Production

```env
LLM_BACKEND="gemini"
GOOGLE_API_KEY="your-production-key"
SECRET_KEY="strong-random-key-64-chars"
RETRIEVAL_ENABLE_NATIVE_RERANK=true
COLLECTION_NAME_ACTIVE="gym_food_hybrid_active"
```

---

## Lien ket

- [Huong dan cai dat](installation.md)
- [Chay nhanh](quickstart.md)
- [Docker Compose](../deployment/docker.md)
