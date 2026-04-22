# Cache va State Management - Quan ly bo nho dem va trang thai

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/cache_service.py`, `app/services/redis_state_service.py`, `app/services/history_service.py`

---

## Tong quan

He thong su dung **ba tang luu tru** phuc vu cac muc dich khac nhau:

| Service | Storage | Muc dich |
|---------|---------|----------|
| `SemanticCacheService` | Qdrant (vector DB) | Cache theo ngu nghia - tim cau hoi tuong tu |
| `RedisStateService` | Redis | Cache chinh xac (SHA-256) + trang thai workflow |
| `HistoryService` | PostgreSQL | Lich su hoi thoai lau dai |

```
Request vao
    |
    v
[SemanticCacheService] -- cosine >= 0.95 --> Tra ve cached answer
    |  (cache miss)
    v
[RedisStateService] -- SHA-256 exact match --> Tra ve cached response
    |  (cache miss)
    v
[Main Pipeline] --> Xu ly --> [HistoryService] Luu vao PostgreSQL
```

---

## 1. SemanticCacheService (Qdrant)

### 1.1 Khoi tao

- Ket noi Qdrant qua `QDRANT_HOST` (mac dinh `localhost`) va `QDRANT_PORT` (mac dinh `6333`).
- Collection: `gym_chat_cache`, vector size = 1024 (tuong thich BGE-M3), distance = COSINE.
- Nguong: **cosine >= 0.95** (rat cao, chi match khi cau hoi gan nhu giong het).
- Lazy loading: Collection chi tao khi lan dau goi `check_cache()` hoac `save_to_cache()`.
- Co `_is_initialized`: Neu Qdrant khong kha dung, cac ham sau se skip (khong crash).

### 1.2 check_cache(vector_query)

Tim cau tra loi da luu bang vector tuong dong:
- Su dung `client.query_points()` voi `score_threshold=0.95`, `limit=1`.
- **CACHE HIT**: Tra ve `hit.payload['answer']`.
- **CACHE MISS**: Tra ve `None`.

### 1.3 save_to_cache(vector_query, question, answer)

Luu cau hoi/tra loi moi vao cache. **Co che bao ve (Safety Guards):**

| Dieu kien | Hanh dong |
|-----------|-----------|
| Answer chua "Loi ket noi", "Error:", "Exception:" | **KHONG LUU** |
| Answer chua "toi chua tim thay thong tin" | **KHONG LUU** |
| Do dai answer < 10 ky tu | **KHONG LUU** |

Payload luu gom: `question`, `answer`, `created_at`. Moi point co ID la UUID v4.

### 1.4 Singleton

```python
cache_service = SemanticCacheService()
```

---

## 2. RedisStateService

### 2.1 Khoi tao

- Ket noi Redis qua `settings.redis_url`, `decode_responses=True`.
- Hai TTL rieng: `EXACT_CACHE_TTL_SECONDS` (cho cache) va `WORKFLOW_STATE_TTL_SECONDS` (cho workflow).
- Co `_available` lam circuit breaker don gian.

### 2.2 _safe(func, default) - Circuit Breaker

Moi thao tac Redis duoc boc trong `_safe()`:
- Neu `_available = False` -> tra ve `default` ngay (khong thu ket noi).
- Neu exception -> dat `_available = False`, tra ve `default`.
- **Luu y:** Mot khi `_available = False`, khong tu phuc hoi. Can restart ung dung.

### 2.3 Exact Cache (SHA-256)

**build_cache_key(payload):** Serialize payload JSON (sorted keys) -> SHA-256 hash -> key `nutrition:cache:{hash}`.

**get_cached_response(payload):** Tim exact match trong Redis. Tra ve `dict` hoac `None`.

**set_cached_response(payload, response_data):** Luu response voi TTL = `EXACT_CACHE_TTL_SECONDS`.

### 2.4 Workflow State

**save_workflow_state(request_id, state_payload):**
- Key: `nutrition:workflow:{request_id}`, TTL: `WORKFLOW_STATE_TTL_SECONDS`.
- Luu trang thai workflow dang chay (ket qua trung gian, buoc hien tai).

**get_workflow_state(request_id):** Lay trang thai. Tra ve `None` neu het TTL.

### 2.5 Redis Key Schema

| Pattern | Muc dich | TTL |
|---------|----------|-----|
| `nutrition:cache:{sha256}` | Exact cache response | `EXACT_CACHE_TTL_SECONDS` |
| `nutrition:workflow:{request_id}` | Workflow state | `WORKFLOW_STATE_TTL_SECONDS` |

### 2.6 Singleton

```python
redis_state_service = RedisStateService()
```

---

## 3. HistoryService (PostgreSQL)

### 3.1 Khoi tao

**Khac hai service tren:** HistoryService **khong la singleton**. Moi request tao instance moi
voi `db_session` rieng (dependency injection cua FastAPI). Su dung hai table: `chat_sessions`, `chat_history`.

### 3.2 Quan ly Session

| Ham | Mo ta |
|-----|-------|
| `create_session(user_id, first_question)` | Tao session moi (ID = UUID v4, title = 50 ky tu dau cua cau hoi) |
| `get_user_sessions(user_id, limit=20, offset=0)` | Lay danh sach sessions, sap xep `updated_at` giam dan |
| `update_session_time(session_id)` | Cap nhat `updated_at = now()` de session len dau list |

### 3.3 Quan ly Message

**get_session_messages(session_id, user_id):**
- **Bao ve quyen rieng tu:** Kiem tra `session.user_id == user_id` truoc. Neu khong khop -> `None`.
- Tra ve list messages format `[{role, content, created_at}, ...]` theo thu tu thoi gian tang dan.

**save_interaction(user_id, session_id, question, answer, sources):** (async)
- Luu cap question/answer vao `chat_history`, `sources` serialize JSON.
- Tu dong goi `update_session_time()`. Co try/except + rollback + close.

### 3.4 Quan ly lich su

| Ham | Mo ta |
|-----|-------|
| `get_user_history(user_id, limit=20, offset=0)` | Lay lich su chat, ho tro pagination |
| `clear_user_history(user_id)` | Xoa toan bo messages + sessions cua user (dung subquery) |

---

## 4. So sanh ba service

| Tieu chi | SemanticCacheService | RedisStateService | HistoryService |
|----------|---------------------|-------------------|----------------|
| Storage | Qdrant (vector) | Redis (key-value) | PostgreSQL (relational) |
| Kieu match | Semantic (cosine) | Exact (SHA-256) | Khong (CRUD) |
| TTL | Khong (vinh vien) | Co (cau hinh) | Khong (vinh vien) |
| Singleton | Co | Co | Khong (per-request) |
| Failure mode | Skip (tra None) | Circuit breaker | Exception + rollback |

---

## 5. Ket noi voi luong chinh

**Chat Q&A Flow (V1/V2):**
```
User hoi -> Embedding -> SemanticCacheService.check_cache()
    |-- HIT --> Tra ve ngay
    |-- MISS --> LLMService -> Tra loi -> save_to_cache() + save_interaction()
```

**Nutrition Workflow (V3):**
```
Request -> RedisStateService.get_cached_response()
    |-- HIT --> Tra ve ngay
    |-- MISS --> Pipeline -> set_cached_response() + save_workflow_state()
```

---

## 6. Luu y thiet ke

- **Graceful degradation:** SemanticCache va Redis deu khong crash khi storage chet.
- **Safety guards:** SemanticCache khong luu response loi vao cache.
- **Privacy:** HistoryService kiem tra `user_id` truoc khi tra messages.
- **Lazy init:** SemanticCache chi tao Qdrant collection khi thuc su can.

---

## Tai lieu lien quan

- [Tong quan kien truc](../architecture/overview.md)
- [Cau hinh he thong](../getting-started/configuration.md)
- [LLM Service](./llm-service.md)
- [Record Policy](./record-policy.md)
- [Evaluation Service](./evaluation-service.md)
