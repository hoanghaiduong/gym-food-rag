# Kien truc Tong quan

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/main.py`, `app/core/config.py`, `docker-compose.yml`

## Gioi thieu

**Gym Food RAG** la backend FastAPI cho bai toan **goi y dinh duong ca nhan hoa** danh cho nguoi tap gym. He thong su dung ky thuat **Retrieval-Augmented Generation (RAG)** ket hop voi **toi uu hoa toan hoc (SciPy)** de tao thuc don chinh xac ve mat dinh duong.

Diem dac biet: thay vi de LLM tu sinh thuc don (de sai so), he thong dung **SciPy least-squares optimizer** de tinh toan chinh xac gram thuc pham, sau do dung LLM chi de **giai thich** ket qua cho nguoi dung.

---

## So do He thong

```
                         +-----------+
                         |  Client   |
                         | (Web/App) |
                         +-----+-----+
                               |
                               v
                    +----------+----------+
                    |    FastAPI Backend   |
                    |   (app/main.py)      |
                    +----------+----------+
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
  +-------+------+    +-------+------+    +--------+-------+
  |  PostgreSQL  |    |    Qdrant    |    |     Redis      |
  |   (Users,    |    | (Vector DB, |    | (Cache, State, |
  |    RBAC,     |    |  Food KB)   |    |  Checkpoints)  |
  |   History)   |    +-------------+    +----------------+
  +--------------+
                               |
                    +----------+----------+
                    |   Ollama / Gemini   |
                    |   (LLM Backend)     |
                    +---------------------+
```

---

## Tech Stack

### Framework & Runtime

| Thanh phan | Cong nghe | Phien ban | Vai tro |
|-----------|-----------|-----------|---------|
| Web Framework | FastAPI | 0.109.0 | API async, auto-docs |
| ASGI Server | Uvicorn | 0.27.0 | HTTP server |
| Data Validation | Pydantic v2 | >=2.7.0 | Schema validation |
| Settings | pydantic-settings | >=2.2.0 | Config tu .env |
| Python | CPython | 3.10+ | Runtime |

### Co so Du lieu

| Service | Image | Port | Vai tro |
|---------|-------|------|---------|
| PostgreSQL 15 | `postgres:15-alpine` | 5432 | Users, RBAC, chat history, system settings |
| Qdrant | `qdrant/qdrant:latest` | 6333 | Vector DB cho food embeddings (hybrid dense+sparse) |
| Redis Stack | `redis/redis-stack:latest` | 6379 | Caching, workflow state, LangGraph checkpoints |
| pgAdmin 4 | `dpage/pgadmin4` | 5050 | Giao dien quan ly PostgreSQL |

### AI / ML / LLM

| Thanh phan | Cong nghe | Mo ta |
|-----------|-----------|-------|
| LLM chinh | Ollama (`qwen2.5:3b`) | LLM local cho sinh thuc don & phan tich intent |
| LLM backup | Google Gemini (`gemini-2.5-flash`) | Cloud LLM fallback |
| Dense Embedding | BAAI/bge-m3 (1024 dims) | Embedding da ngon ngu cho semantic search |
| Sparse Embedding | Vietnamese Lexical Encoder | Bigram hashing cho keyword matching tieng Viet |
| Reranking | BGE-M3 native (colbert+sparse+dense) | Cross-encoder reranking |
| Agent | LangGraph + LangChain | Agent hoi thoai voi tool-calling |
| Toi uu hoa | SciPy `least_squares` | Linear programming toi uu gram thuc pham |

### Security

| Thanh phan | Cong nghe | Chi tiet |
|-----------|-----------|----------|
| Authentication | JWT (HS256) | Access token 30 phut, refresh token 7 ngay |
| Password | bcrypt (`passlib`) | Hash mat khau |
| Authorization | RBAC | Roles: Admin, Editor, user; Permissions granular |

---

## Cau truc Thu muc

```
gym-food-rag/
├── app/                     # CORE APPLICATION
│   ├── main.py              # FastAPI app factory, lifespan, CORS
│   ├── api/                 # API Layer (V1, V2, V3 routers)
│   │   ├── router.py        # Central router mount
│   │   ├── deps.py          # Dependencies (DB, auth, permissions)
│   │   ├── v1/              # Legacy chat endpoint
│   │   ├── v2/              # Setup wizard, system, admin
│   │   └── v3/              # Current: auth, chat, nutrition, RBAC, users
│   ├── core/                # Infrastructure
│   │   ├── config.py        # Pydantic Settings (tat ca env vars)
│   │   ├── security.py      # JWT, bcrypt
│   │   ├── redis.py         # Redis async pool
│   │   ├── response.py      # Chuan hoa JSON response
│   │   ├── exceptions.py    # Global error handlers
│   │   └── paths.py         # Project path constants
│   ├── db/                  # Database
│   │   ├── tables/          # SQLAlchemy table definitions
│   │   ├── migrations.py    # Auto-sync columns (custom migration)
│   │   └── seeds.py         # Seed data (roles, permissions, admin)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic (15+ services)
│   │   ├── nutrition_workflow_service.py   # Orchestrator chinh
│   │   ├── nutrition_knowledge_service.py  # Qdrant hybrid search
│   │   ├── embedding_bge_service.py        # BGE-M3 embeddings
│   │   ├── nutrition_intent_service.py     # Intent parsing
│   │   ├── nutrition_service.py            # TDEE + SciPy optimizer
│   │   ├── ollama_nutrition_service.py     # LLM abstraction
│   │   └── v3/              # LangGraph agent
│   └── modules/users/       # Modular user management
├── scripts/                 # Data pipeline & CLI tools
├── data/                    # Nutrition data (raw + processed)
├── docs/                    # Tai lieu (ban dang doc day)
├── assets/                  # Hinh anh thuc pham
├── storage/                 # Docker volumes (git-ignored)
└── docker-compose.yml       # Infrastructure services
```

---

## Nguyen tac Thiet ke

### 1. Deterministic-first, LLM-explain
Thuc don duoc tinh toan bang **SciPy optimizer** (chinh xac ve calo/macro), LLM chi dung de **giai thich** ket qua. Khong de LLM tu sinh thuc don vi de sai so dinh duong.

### 2. Hybrid RAG
Ket hop **dense search** (BGE-M3 semantic) va **sparse search** (Vietnamese lexical) de tim thuc pham chinh xac ca ve ngu nghia lan tu khoa.

### 3. Bilingual Normalization
Moi lookup map deu ho tro ca tieng Viet va tieng Anh: `"giam can"` -> `"lose_weight"`, `"tang co"` -> `"gain_muscle"`.

### 4. Fallback Chains
Moi buoc deu co fallback: LLM giai thich -> text deterministic; Native rerank -> lexical+dense; Qdrant -> local JSONL index.

### 5. API Versioning
V1 (basic RAG) -> V2 (auth + RBAC) -> V3 (nutrition workflows, LangGraph agent). Chi V2 setup/system + V3 dang active.

### 6. Singleton Services
Tat ca services deu dung singleton pattern de tiet kiem tai nguyen: `llm_service`, `bge_service`, `cache_service`, etc.

---

## Lien ket

- [Pipeline RAG chi tiet](rag-pipeline.md)
- [Luong du lieu end-to-end](data-flow.md)
- [Huong dan cai dat](../getting-started/installation.md)
- [API Reference](../api/overview.md)
