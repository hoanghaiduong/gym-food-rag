# Code Style & Patterns

> Cap nhat lan cuoi: 2026-04-06

## Python Style

### Formatter & Linter

Khuyen nghi su dung:
- **Black** — Code formatter (line length 100)
- **isort** — Import sorting
- **flake8** hoac **ruff** — Linter

```powershell
pip install black isort ruff
black app/ scripts/ --line-length 100
isort app/ scripts/
ruff check app/ scripts/
```

---

## Patterns Su dung trong Du an

### 1. Singleton Pattern (Module-level Instances)

Tat ca services deu khoi tao **1 instance duy nhat** o cuoi file:

```python
# app/services/nutrition_service.py
class NutritionService:
    def __init__(self):
        self.activity_multipliers = {...}
    
    def calculate_tdee(self, ...): ...

# Singleton instance — import truc tiep
nutrition_service = NutritionService()
```

**Su dung:**
```python
from app.services.nutrition_service import nutrition_service
result = nutrition_service.calculate_tdee(...)
```

**Tai sao:** Tranh tao nhieu instance, tiet kiem RAM (dac biet cho embedding models ~2 GB).

### 2. Bilingual Normalization Maps

Tat ca user input duoc normalize qua map song ngu:

```python
GOAL_MAP = {
    # Tieng Viet
    "giam_can": "lose_weight",
    "giam can": "lose_weight",
    "tang co": "gain_muscle",
    # Tieng Anh
    "cutting": "lose_weight",
    "bulking": "gain_muscle",
    # Canonical
    "lose_weight": "lose_weight",
}
```

**Quy tac:** Moi map phai bao gom ca tieng Viet (khong dau), tieng Anh, va canonical value.

### 3. Factory Pattern (Embedding)

```python
# app/services/embedding_factory.py
def get_embedding_service():
    if settings.USE_LOCAL_EMBEDDING:
        return get_bge_service()
    else:
        return GeminiEmbeddingService()
```

### 4. Fallback Chains

Moi operation quan trong deu co fallback:

```python
try:
    # Primary: LLM-based intent parsing
    intent = await llm_parse_intent(instruction)
except Exception:
    # Fallback: Rule-based parsing
    intent = rule_based_parse(instruction)
```

**Pattern thuong gap:**
- LLM generate -> Deterministic text template
- Native rerank -> Dense + lexical scoring
- Qdrant search -> Local JSONL index

### 5. Pydantic Schema Pattern

```python
# Request schema — khai bao validation
class NutritionRecommendationRequest(BaseModel):
    instruction: Optional[str] = None
    meal_count: int = Field(default=3, ge=3, le=5)
    top_k: int = Field(default=18, ge=6, le=40)

# Response schema — Generic BaseResponse
class BaseResponse(BaseModel, Generic[T]):
    status: str = "success"
    code: int = 200
    message: str = "Success"
    data: Optional[T] = None
    meta: Optional[MetaData] = None
```

### 6. SQLAlchemy Core (Table-level)

Du an su dung **SQLAlchemy Core** (khong phai ORM):

```python
# Dinh nghia table (khong phai class)
users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(50), unique=True),
    ...
)

# Query
result = db.execute(select(users).where(users.c.id == user_id))
user = result.mappings().first()
```

**Tai sao:** Nhe hon ORM, du manh cho du an nay, de control SQL.

### 7. Dependency Injection (FastAPI Depends)

```python
@router.get("/profile")
async def get_profile(
    current_user = Depends(PermissionChecker("user.profile")),
    db: Session = Depends(get_db)
):
    ...
```

---

## Code Organization Rules

### Imports

```python
# 1. Standard library
import json
import logging
from datetime import datetime

# 2. Third-party
from fastapi import APIRouter, Depends
from pydantic import BaseModel

# 3. Local (absolute paths)
from app.core.config import settings
from app.services.nutrition_service import nutrition_service
```

### Logging

```python
import logging
logger = logging.getLogger(__name__)

# Su dung
logger.info("Processing request %s", request_id)
logger.error("Failed to parse intent: %s", str(e), exc_info=True)
```

### Type Hints

Dung type hints cho tat ca function parameters va return types:

```python
def calculate_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str
) -> float:
    ...
```

---

## Files Thuong gap

| Pattern | Vi du | Muc dich |
|---------|-------|----------|
| `app/services/*_service.py` | `nutrition_service.py` | Business logic |
| `app/schemas/*.py` | `nutrition.py` | Pydantic schemas |
| `app/api/v3/*.py` | `nutrition.py` | API endpoints |
| `app/db/tables/*.py` | `users.py` | Table definitions |
| `scripts/*.py` | `ingest_v3.py` | CLI tools |

---

## Lien ket

- [Huong dan dong gop](guidelines.md)
- [Kien truc tong quan](../architecture/overview.md)
