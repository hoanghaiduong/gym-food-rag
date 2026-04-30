# Nutrition V3 Endpoints

> Cap nhat lan cuoi: 2026-04-28
> Source code: `app/api/v3/nutrition.py`, `app/schemas/nutrition.py`, `app/services/nutrition/orchestration/`

## Tong quan

API Nutrition V3 la **core** cua he thong — cung cap goi y dinh duong ca nhan hoa dua tren ho so nguoi dung. Tat ca endpoint yeu cau JWT authentication.

---

## Endpoints

### GET /api/v3/nutrition/profile

Lay ho so dinh duong cua user hien tai.

**Permission:** `user.profile`

**Response Schema:** `NutritionProfile`

```json
{
  "status": "success",
  "data": {
    "user_id": 1,
    "username": "admin",
    "full_name": "Super Administrator",
    "age": 25,
    "gender": "male",
    "weight": 70.0,
    "height": 175.0,
    "activity_level": "moderate",
    "dietary_preference": "omnivore",
    "allergies": "shellfish",
    "target_goal": "gain_muscle",
    "allergy_tags": ["shellfish"]
  }
}
```

---

### PUT /api/v3/nutrition/profile

Cap nhat ho so dinh duong. He thong tu dong normalize gia tri (VD: `"nam"` -> `"male"`).

**Permission:** `user.profile`

**Request Schema:** `NutritionProfileUpdate`

```json
{
  "age": 25,
  "gender": "nam",
  "weight": 70,
  "height": 175,
  "activity_level": "vua",
  "dietary_preference": "an_tap",
  "allergies": ["tom", "cua"],
  "target_goal": "tang_co"
}
```

**Validation:**
- `age`: 10 - 100
- `weight`: 20 - 400 kg
- `height`: 100 - 250 cm

---

### POST /api/v3/nutrition/recommendation

**Endpoint chinh** — Tao goi y thuc don ca nhan hoa.

**Permission:** `chat.use`

**Request Schema:** `NutritionRecommendationRequest`

```json
{
  "instruction": "Toi muon giam can, khong an hai san, thich mon don gian",
  "meal_count": 3,
  "top_k": 18,
  "max_revision_rounds": 3,
  "calorie_tolerance_pct": 0.10,
  "macro_tolerance_pct": 0.15,
  "use_cache": true,
  "include_debug": false,
  "excluded_foods": ["banh mi", "mi tom"],
  "must_include": ["uc ga", "com gao lut"]
}
```

**Request Parameters:**

| Field | Type | Default | Range | Mo ta |
|-------|------|---------|-------|-------|
| `instruction` | str? | null | — | Huong dan tu nhien (tieng Viet/Anh) |
| `meal_count` | int | 3 | 3-5 | So bua an |
| `top_k` | int | 18 | 6-40 | So thuc pham ung vien |
| `max_revision_rounds` | int | 3 | 0-4 | So lan thu lai neu validation fail |
| `calorie_tolerance_pct` | float | 0.10 | 0-0.30 | Sai so calo chap nhan (%) |
| `macro_tolerance_pct` | float | 0.15 | 0-0.40 | Sai so macro chap nhan (%) |
| `use_cache` | bool | true | — | Su dung cache Redis |
| `include_debug` | bool | false | — | Tra ve debug info |
| `excluded_foods` | list[str] | [] | — | Thuc pham loai tru |
| `must_include` | list[str] | [] | — | Thuc pham bat buoc co |

**Response Schema:** `NutritionRecommendationResponse`

```json
{
  "status": "success",
  "data": {
    "request_id": "uuid-...",
    "cached": false,
    "engine": {"llm": "ollama/qwen2.5:3b", "embedding": "bge-m3"},
    "profile": { ... },
    "targets": {
      "tdee": 2500,
      "daily_calories": 2800,
      "protein_g": 175,
      "carbs_g": 350,
      "fat_g": 78,
      "meal_targets": [
        {"name": "Breakfast", "ratio": 0.28, "calories": 784, ...},
        {"name": "Lunch", "ratio": 0.37, "calories": 1036, ...},
        {"name": "Dinner", "ratio": 0.35, "calories": 980, ...}
      ]
    },
    "plan": {
      "summary": "Thuc don 3 bua tang co ...",
      "reasoning": ["Uu tien protein cao", "Carb phuc tap"],
      "meals": [
        {
          "meal_name": "Breakfast",
          "explanation": "Bua sang giau protein...",
          "items": [
            {"food_name": "Yen mach", "grams": 80},
            {"food_name": "Trung ga luoc", "grams": 150}
          ]
        }
      ]
    },
    "resolved_meals": [ ... ],
    "totals": {"energy_kcal": 2780, "protein_g": 172, "carbs_g": 345, "fat_g": 76},
    "validation": {
      "passed": true,
      "attempt": 1,
      "calorie_error_pct": 0.007,
      "macro_deviation_pct": 0.03,
      "violation_rate": 0.0,
      "issues": []
    },
    "retrieved_context": [ ... ],
    "grounded_foods": [ ... ],
    "revisions_used": 0,
    "response_time_seconds": 12.5,
    "workflow_trace": [ ... ]
  }
}
```

---

### POST /api/v3/nutrition/recommendation-agent

**Endpoint shadow LangGraph** - dung cho demo luan van, orchestration/chat trace va so sanh. Endpoint nay khong thay the endpoint production `/recommendation`.

**Permission:** `chat.use`

**Request Schema:** `NutritionAgentRecommendationRequest`

Schema nay ke thua `NutritionRecommendationRequest` va them `session_id` de checkpoint/trace hoi thoai.

```json
{
  "session_id": "demo-session-001",
  "instruction": "Toi muon tang co, khong an hai san, uu tien bua don gian",
  "meal_count": 3,
  "top_k": 18,
  "max_revision_rounds": 3,
  "use_cache": true,
  "must_include": ["uc ga", "com gao lut"]
}
```

**Safety contract:**

| Rule | Mo ta |
|------|------|
| Core decision only | LangGraph chi goi `recommend_nutrition_plan_tool`, tool nay delegate vao `NutritionWorkflowService.run_main_flow()`. |
| No direct food tools | Agent recommendation khong expose `search_gym_food` hoac `optimize_meal_plan`. |
| No LLM final plan | LLM chi hoi lai/dien giai, khong duoc tu tao danh sach mon final. |
| Validation gate | Neu core validation fail hoac co unsafe item, `recommendation=null` va `status=needs_revision`. |
| Safe labels | Mon hien thi phai den tu core response da validate va policy `safe_display_name`. |

**Response Schema:** `NutritionAgentRecommendationResponse`

```json
{
  "status": "success",
  "data": {
    "session_id": "demo-session-001",
    "answer": "Minh da tao thuc don 3 bua...",
    "recommendation": {
      "request_id": "uuid-...",
      "validation": {"passed": true},
      "plan": {"meals": []}
    },
    "orchestration_trace": [
      {"node": "normalize_request", "status": "completed"},
      {"node": "clarify_intent", "status": "completed"},
      {"node": "run_core_recommendation", "status": "completed"},
      {"node": "inspect_validation", "status": "completed"},
      {"node": "generate_explanation", "status": "completed"},
      {"node": "finalize_response", "status": "completed"}
    ],
    "engine": {
      "orchestrator": "langgraph",
      "tooling": "langchain_structured_tool",
      "decision_engine": "NutritionWorkflowService",
      "decision_contract": "validated_core_response_only",
      "llm_role": "intent_clarification_and_explanation_only"
    },
    "validation_passed": true,
    "status": "completed"
  }
}
```

Neu can hoi lai thong tin, response co `status=needs_clarification` va `recommendation=null`. Neu core engine khong validate duoc plan, response co `status=needs_revision` va agent khong tu bia plan thay the.

---

### GET /api/v3/nutrition/workflows/{request_id}

Lay trang thai workflow tu Redis (debug/monitoring).

**Permission:** `chat.use`

```json
{
  "status": "success",
  "data": {
    "request_id": "uuid-...",
    "status": "completed",
    "payload": {
      "trace": [...],
      "response_excerpt": { ... }
    }
  }
}
```

---

### POST /api/v3/nutrition/evaluate

A/B testing: chay 3 phuong an song song va so sanh.

**Permission:** `chat.use`

**Request:** Giong `NutritionRecommendationRequest`

**Response Schema:** `NutritionEvaluationResponse`

```json
{
  "status": "success",
  "data": {
    "request_id": "uuid-...",
    "created_at": "2026-04-06T10:00:00Z",
    "profile": { ... },
    "targets": { ... },
    "variants": [
      {"name": "main_flow", "passed": true, "calorie_error_pct": 0.02, ...},
      {"name": "pure_generation", "passed": false, "calorie_error_pct": 0.15, ...},
      {"name": "rule_based", "passed": true, "calorie_error_pct": 0.05, ...}
    ],
    "best_variant": "main_flow",
    "log_path": "logs/nutrition_evaluations.jsonl"
  }
}
```

---

## Lien ket

- [NutritionWorkflowService](../services/nutrition-workflow.md)
- [Luong du lieu](../architecture/data-flow.md)
- [Authentication](authentication.md)
