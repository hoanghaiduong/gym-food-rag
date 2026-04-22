# Chat V3 Endpoints

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/api/v3/chat_v3.py`

## Tong quan

Chat V3 su dung **LangGraph Agent** voi **Semantic Cache** (Qdrant) de xu ly cau hoi ve dinh duong.

> **Trang thai:** Endpoint da duoc viet nhung **chua mount** trong `app/api/router.py` hien tai. Agent service la placeholder (`agent_service_v3 = None`). Luong nutrition chinh dung `/api/v3/nutrition/recommendation`.

---

## Endpoint

### POST /api/v3/chat

**Permission:** `chat.use`

**Request:**

```json
{
  "question": "Uc ga bao nhieu calo?",
  "session_id": null
}
```

| Field | Type | Default | Mo ta |
|-------|------|---------|-------|
| `question` | str | required | Cau hoi cua nguoi dung |
| `session_id` | str? | null | ID session (null = tao moi) |

**Response:**

```json
{
  "status": "success",
  "data": {
    "answer": "Uc ga luoc chua khoang 165 kcal/100g...",
    "session_id": "uuid-...",
    "engine": "Redis Cache (Fast)",
    "context_used": ["Redis Semantic Cache"]
  }
}
```

---

## Luong Xu ly

```
1. Semantic Cache Check (Qdrant)
   |-- Dense embed query
   |-- cosine similarity >= 0.95?
   |   |-- YES: Return cached answer
   |   |-- NO: Continue
   |
2. Build User Profile
   |-- Calculate TDEE & macros (if enough data)
   |-- Inject into user_dict
   |
3. LangGraph Agent
   |-- System prompt dong (user context)
   |-- Agent loop:
   |   |-- LLM suy nghi
   |   |-- Tool call? -> Execute tool -> Loop
   |   |-- No tool -> Final answer
   |
4. Hau xu ly
   |-- Luu vao Semantic Cache (Qdrant)
   |-- Luu vao Chat History (PostgreSQL, background task)
```

---

## So sanh Chat V3 vs Nutrition V3

| Tieu chi | Chat V3 | Nutrition V3 |
|---------|---------|--------------|
| Tinh chat | Hoi thoai tu nhien | Goi y thuc don co cau truc |
| Engine | LangGraph Agent (LLM quyetdinh) | Deterministic pipeline (SciPy) |
| Do chinh xac | Phu thuoc LLM | Chinh xac cao (mathematical) |
| Cache | Semantic (Qdrant cosine) | Exact (Redis SHA-256) |
| Multi-turn | Co (Redis checkpoints) | Khong (single-shot) |
| Trang thai | Chua active | **Active** |

---

## Lien ket

- [LangGraph Agent](../architecture/langgraph-agent.md)
- [Cache & State](../services/cache-state.md)
- [Tong quan API](overview.md)
