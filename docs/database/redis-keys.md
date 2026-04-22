# Redis Keys & Patterns

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/services/redis_state_service.py`, `app/services/cache_service.py`, `app/core/redis.py`

## Tong quan

Redis duoc dung cho 3 muc dich chinh:
1. **Exact cache** — Cache ket qua nutrition recommendation
2. **Workflow state** — Luu trang thai debug cua moi request
3. **LangGraph checkpoints** — Memory hoi thoai cua agent

---

## Exact Cache (Nutrition Recommendations)

| Thuoc tinh | Gia tri |
|-----------|---------|
| **Key pattern** | `nutrition:cache:{sha256_hash}` |
| **Hash input** | SHA-256 cua JSON payload request |
| **Value** | JSON ket qua recommendation |
| **TTL** | 900 giay (15 phut) — `EXACT_CACHE_TTL_SECONDS` |

### Cach Hash Key

```python
# RedisStateService.build_cache_key()
payload = {
    "user_id": user_id,
    "instruction": instruction,
    "meal_count": meal_count,
    "top_k": top_k,
    "excluded_foods": sorted(excluded_foods),
    "must_include": sorted(must_include),
    # ... tat ca tham so anh huong ket qua
}
json_str = json.dumps(payload, sort_keys=True)
hash = hashlib.sha256(json_str.encode()).hexdigest()
key = f"nutrition:cache:{hash}"
```

### Logic Cache

```
Request den
  |
  v
Build cache key (SHA-256 cua payload)
  |
  v
Redis GET key
  |-- Hit -> Tra ve ket qua (gan cached=true)
  |-- Miss -> Chay full pipeline
  |           -> Neu validation pass: Redis SET key (TTL 900s)
  v
Return response
```

---

## Workflow State (Debug/Monitoring)

| Thuoc tinh | Gia tri |
|-----------|---------|
| **Key pattern** | `workflow:{request_id}` |
| **Value** | JSON object voi trace info |
| **TTL** | 3600 giay (1 gio) — `WORKFLOW_STATE_TTL_SECONDS` |

### Noi dung State

```json
{
  "status": "completed",
  "request_id": "uuid-...",
  "started_at": "2026-04-06T10:00:00Z",
  "completed_at": "2026-04-06T10:00:12Z",
  "trace": [
    {"step": "parse_intent", "duration_ms": 150, "result": "..."},
    {"step": "compute_tdee", "duration_ms": 2, "result": "..."},
    {"step": "retrieve_candidates", "duration_ms": 800, "result": "..."},
    {"step": "optimize_pool", "duration_ms": 50, "result": "..."},
    {"step": "scipy_optimize", "duration_ms": 200, "result": "..."},
    {"step": "validate", "duration_ms": 5, "result": "..."},
    {"step": "llm_explain", "duration_ms": 8000, "result": "..."}
  ],
  "response_excerpt": { ... }
}
```

### Truy xuat State

```bash
# Qua API
GET /api/v3/nutrition/workflows/{request_id}
```

---

## LangGraph Checkpoints

| Thuoc tinh | Gia tri |
|-----------|---------|
| **Library** | `langgraph-checkpoint-redis` |
| **Key pattern** | Quan ly boi `AsyncRedisSaver` |
| **TTL** | ~7 ngay |
| **Muc dich** | Luu lich su hoi thoai multi-turn |

Can goi `await checkpointer.setup()` khi server start de tao Redis Search Index.

---

## Cau hinh Redis

### Docker

```yaml
redis:
  image: redis/redis-stack:latest
  container_name: gym_redis
  ports:
    - "6379:6379"    # Redis CLI
    - "8001:8001"    # Redis Insight UI
  volumes:
    - ./storage/redis:/data
```

### Redis Insight

Truy cap: **http://localhost:8001** de monitor keys, memory, va throughput.

### Bien moi truong

| Bien | Mac dinh | Mo ta |
|------|----------|-------|
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_URL` | `redis://localhost:6379/0` | Full URL (uu tien) |
| `EXACT_CACHE_TTL_SECONDS` | `900` | TTL nutrition cache |
| `WORKFLOW_STATE_TTL_SECONDS` | `3600` | TTL workflow state |

---

## Tong hop Key Patterns

| Pattern | TTL | Muc dich |
|---------|-----|----------|
| `nutrition:cache:{sha256}` | 15 phut | Cache ket qua nutrition |
| `workflow:{uuid}` | 1 gio | Debug trace |
| LangGraph internal | 7 ngay | Chat memory |

---

## Lien ket

- [Cache & State Service](../services/cache-state.md)
- [Cau hinh](../getting-started/configuration.md)
- [Docker Compose](../deployment/docker.md)
