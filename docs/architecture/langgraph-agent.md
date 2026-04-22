# LangGraph Agent V3

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/services/v3/agent.py`, `app/services/v3/tools.py`, `app/services/v3/state.py`

## Tong quan

LangGraph Agent V3 la **agent hoi thoai** su dung framework **LangGraph** (tu LangChain) de xu ly cau hoi cua nguoi dung ve dinh duong. Agent co kha nang:
- Tra cuu thuc pham tu Qdrant (hybrid search)
- Tinh toan luong gram toi uu bang SciPy
- Duy tri lich su hoi thoai qua nhieu luot (multi-turn) voi Redis checkpoints

> **Trang thai hien tai:** Agent dang o che do **placeholder** (`agent_service_v3 = None`). Luong nutrition chinh su dung `NutritionWorkflowService` thay the.

---

## Kien truc Graph

```
                    +--------+
                    | START  |
                    +--------+
                        |
                        v
                  +-----------+
            +---->|   Agent   |<----+
            |     | (LLM node)|     |
            |     +-----------+     |
            |          |            |
            |    tools_condition    |
            |     /          \     |
            |   Co tool       Khong tool
            |   call          call
            |    |                |
            |    v                v
            | +-------+     +--------+
            | | Tools |     |  END   |
            | | Node  |     +--------+
            | +-------+
            |    |
            +----+ (lap lai)
```

### Cac Node

| Node | Vai tro | Source |
|------|---------|--------|
| `agent` | Goi LLM voi messages + system prompt dong | `GymAgentV3.call_model()` |
| `tools` | Thuc thi tool duoc LLM chon | `ToolNode(agent_tools)` |

### Conditional Edges
- `tools_condition`: Kiem tra LLM response co chua tool call khong
  - **Co** -> chuyen den `tools` node
  - **Khong** -> ket thuc (END)

---

## Agent State

```python
# app/services/v3/state.py
class AgentState(TypedDict):
    messages: Annotated[List, add_messages]  # Lich su hoi thoai
    user_profile: Dict[str, Any]             # Ho so nguoi dung
```

- `messages`: Danh sach messages voi `add_messages` reducer (tu dong noi them, khong ghi de)
- `user_profile`: Thong tin nguoi dung (age, weight, goal, allergies, tdee, macros)

---

## Dynamic System Prompt

Agent tao system prompt **dong** dua tren `user_profile`:

```
[HARDCORE_SYSTEM_PROMPT]  # Prompt co dinh ve vai tro AI dinh duong

[USER CONTEXT]
- Do tuoi: 25
- Can nang: 70 kg
- Muc tieu: Tang co
- Di ung: Khong
- Che do an uu tien: An tap
- Tong Calo tieu hao (TDEE): 2500 kcal
- Macro toi uu/ngay: 2800 kcal, Dam: 175g, Carb: 350g, Beo: 78g
```

System prompt duoc **cap nhat moi luot hoi thoai** de dam bao context moi nhat.

---

## Agent Tools

### 1. `search_gym_food(query: str)`

**Muc dich:** Tra cuu thong tin dinh duong cua thuc pham.

**Khi nao su dung:** User hoi ve calo, protein, thanh phan, goi y mon an, so sanh mon an.

**Hoat dong:**
1. Encode query thanh hybrid embedding (BGE-M3)
2. Query Qdrant voi prefetch dense + sparse
3. Fusion: RRF (Reciprocal Rank Fusion)
4. Tra ve top 5 ket qua dang text

```python
# Vi du input/output:
search_gym_food("uc ga luoc")
# Output: "- Uc ga luoc: 165 kcal/100g, Protein: 31g, Carb: 0g, Fat: 3.6g..."
```

### 2. `optimize_meal_plan(food_keywords, target_calories, target_protein, target_carbs, target_fat)`

**Muc dich:** Tinh toan chinh xac so gram cho moi thuc pham de dat muc tieu dinh duong.

**Hoat dong:**
1. Tim moi thuc pham trong Qdrant (dense search, limit=1)
2. Trich xuat thong tin dinh duong tu payload
3. Goi `NutritionService.optimize_meal()` (SciPy least-squares)
4. Tra ve ket qua gram chinh xac

```python
# Vi du:
optimize_meal_plan(
    food_keywords=["com trang", "uc ga luoc", "rau muong"],
    target_calories=600,
    target_protein=40,
    target_carbs=70,
    target_fat=15
)
# Output:
# KET QUA TINH TOAN:
# - Com trang: 180g (Calo: 234 kcal, Pro: 4.3g, Carb: 51.5g, Fat: 0.5g)
# - Uc ga luoc: 120g (Calo: 198 kcal, Pro: 37.2g, Carb: 0g, Fat: 4.3g)
# - Rau muong: 200g (Calo: 38 kcal, Pro: 2.6g, Carb: 5.8g, Fat: 0.4g)
# TONG BUA NAY: 470 kcal | Pro: 44.1g | Carb: 57.3g | Fat: 5.2g
```

---

## LLM Backend

| Backend | Class | Model | Trang thai |
|---------|-------|-------|------------|
| Ollama | `ChatOllama` | `qwen2.5:3b` | **Active** |
| Gemini | `ChatGoogleGenerativeAI` | `gemini-2.5-flash` | Commented out |

Cau hinh hien tai:
```python
self.llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0,
    keep_alive="5m"
)
self.llm_with_tools = self.llm.bind_tools(tools=agent_tools)
```

---

## Conversation Memory (Redis)

- **Checkpointer:** `AsyncRedisSaver` tu `langgraph-checkpoint-redis`
- **Key:** `thread:{session_id}`
- **Serialization:** `pickle`
- **TTL:** 7 ngay tu dong xoa
- **Khoi tao:** Phai goi `await agent.initialize()` khi server start de tao Redis Search Index

```python
# Moi cuoc hoi thoai duoc theo doi bang session_id
config = {"configurable": {"thread_id": session_id}}
```

---

## Xu ly Loi

| Loi | Xu ly |
|-----|-------|
| Recursion limit (10 buoc) | Tra ve thong bao "yeu cau qua phuc tap" |
| Tool execution error | Tra ve `SYSTEM_ERROR: ...` cho LLM xu ly |
| Qdrant connection fail | Tra ve "Khong tim thay mon an" |
| LLM timeout | Raise exception len API layer |

---

## So sanh voi Nutrition Workflow

| Tieu chi | LangGraph Agent V3 | NutritionWorkflowService |
|---------|-------------------|--------------------------|
| Tinh chat | Hoi thoai, nhieu luot | Single-shot recommendation |
| Do chinh xac | LLM quyet dinh (co the sai) | Deterministic (SciPy toi uu) |
| Tool calling | Agent tu chon tool | Pipeline co dinh |
| Memory | Redis checkpoints | Khong co |
| Trang thai | Placeholder | **Active** |
| Phu hop cho | Chat tu nhien | Goi y thuc don chinh xac |

---

## Lien ket

- [Luong du lieu end-to-end](data-flow.md)
- [BGEEmbeddingService](../services/embedding-service.md)
- [NutritionService](../services/nutrition-optimizer.md)
- [Cache & State](../services/cache-state.md)
