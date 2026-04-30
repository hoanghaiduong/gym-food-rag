# Luong Du lieu End-to-End

> Cap nhat lan cuoi: 2026-04-28
> Source code: `app/services/nutrition_workflow_service.py`, `app/services/nutrition/orchestration/`, `app/api/v3/nutrition.py`

## Luong Goi y Dinh duong (Core Flow)

Day la luong xu ly chinh cua he thong khi nguoi dung yeu cau goi y thuc don:

```
POST /api/v3/nutrition/recommendation
    |
    v
[1] Auth & Permission Check
    | JWT -> PermissionChecker("chat.use")
    v
[2] Build User Profile
    | Normalize: gender, activity, dietary, allergies
    | Maps song ngu: "giam_can" -> "lose_weight"
    v
[3] Redis Cache Check
    | SHA-256 hash cua payload -> exact match
    | Hit -> tra ve ngay (TTL: 900s)
    v
[4] Parse Intent (NutritionIntentService)
    | Input: "Toi muon giam can, khong an hai san"
    | -> LLM parsing (Ollama/Gemini)
    | -> Rule-based fallback (regex, keywords)
    | Output: NutritionIntent (goal, constraints, preferences)
    v
[5] Compute TDEE & Macro Targets
    | Mifflin-St Jeor: BMR * activity_factor
    | Goal adjustment: lose_weight (-500 kcal), gain_muscle (+300 kcal)
    | Macro split: protein/carbs/fat % theo goal
    | Chia theo bua: MEAL_TEMPLATES (3/4/5 bua)
    v
[6] Retrieve Food Candidates (CanonicalKnowledgeService)
    | Pass 1: must_include items (KHONG loc diet filter)
    | Pass 2: regular retrieval (CO loc diet/allergen)
    | Hybrid search: dense + sparse -> RRF -> rerank
    v
[7] Optimize Candidate Pool
    | Goal-fit scoring (protein density, energy, fiber...)
    | Realism filtering (block condiments, spices, raw)
    | Role quotas: N protein anchors, N carb, N produce
    | Dedup by name/entity_id
    v
[8] Deterministic Meal Planning (SciPy)
    | NutritionService.optimize_meal()
    | SciPy least_squares: min ||f(grams) - targets||^2
    | Bounds: 30g - 400g moi thuc pham
    | Resolve items against knowledge base
    v
[9] Validation
    | Calorie error % <= tolerance
    | Macro deviation % <= tolerance
    | Allergen compliance check
    | Dietary compliance check
    v
[10] LLM Explanation (Ollama/Gemini)
     | Input: deterministic plan + user context
     | Output: summary, reasoning, per-meal explanations
     | Fallback: deterministic text neu LLM fail
     v
[11] Compose Response & Cache
     | Final: plan + validation + context + trace
     | Cache ket qua valid trong Redis
     v
Return NutritionRecommendationResponse
```

---

## Chi tiet Tung Buoc

### Buoc 2: Build User Profile

He thong normalize tat ca thong tin tu database sang dang chuan bang cac map song ngu:

| Map | Vi du input | Output |
|-----|-------------|--------|
| `GOAL_MAP` | `"giam_can"`, `"cutting"`, `"fat_loss"` | `"lose_weight"` |
| `GENDER_MAP` | `"nam"`, `"male"`, `"man"` | `"male"` |
| `ACTIVITY_MAP` | `"nhe"`, `"light"` | `"light"` |
| `DIETARY_MAP` | `"an_chay"`, `"vegetarian"` | `"vegetarian"` |
| `ALLERGY_MAP` | `"tom"`, `"cua"`, `"shellfish"` | `"shellfish"` |

### Buoc 5: MEAL_TEMPLATES

Phan bo calo theo so bua:

| 3 bua | 4 bua | 5 bua |
|-------|-------|-------|
| Breakfast: 28% | Breakfast: 25% | Breakfast: 22% |
| Lunch: 37% | Lunch: 30% | Morning Snack: 10% |
| Dinner: 35% | Dinner: 30% | Lunch: 28% |
| | Snack: 15% | Dinner: 28% |
| | | Evening Snack: 12% |

### Buoc 7: Goal-fit Scoring

Moi thuc pham duoc cham diem da yeu to:

```
score = protein_density_score
      + energy_score
      + fiber_score
      + diet_tag_bonus
      + must_include_bonus
      - practicality_penalty
      + intent_alignment_score
```

`intent_alignment_score` dua vao:
- Cooking complexity preference
- Budget preference
- Meal style (nhieu mon nho vs it mon lon)
- Pre/post workout timing

---

## Luong Shadow LangGraph Nutrition Agent

```
POST /api/v3/nutrition/recommendation-agent
    |
    v
[1] Auth & Permission Check
    | JWT -> PermissionChecker("chat.use")
    v
[2] normalize_request
    | Tach session_id, chuan hoa payload ve NutritionRecommendationRequest
    v
[3] clarify_intent
    | Co the hoi lai neu request qua mo ho
    | LLM chi phuc vu hoi thoai/dien giai, khong quyet dinh mon final
    v
[4] run_core_recommendation
    | LangChain tool duy nhat: recommend_nutrition_plan_tool
    | Tool delegate vao NutritionWorkflowService.run_main_flow()
    v
[5] NutritionWorkflowService
    | Qdrant retrieval -> macro targets -> optimization -> validation
    v
[6] inspect_validation
    | Neu validation fail hoac co unsafe item -> needs_revision
    | Khong cho LLM tu sua bang mon ngoai candidate pool
    v
[7] generate_explanation
    | Dien giai plan da validate bang text an toan
    v
[8] finalize_response
    | recommendation = core NutritionRecommendationResponse neu validation_passed=true
    | recommendation = null neu needs_clarification/needs_revision
    v
Return NutritionAgentRecommendationResponse
```

LangGraph trong flow nay la lop orchestration/chat shadow de demo va so sanh theo de tai. Endpoint production `POST /api/v3/nutrition/recommendation` van di thang vao `NutritionWorkflowService` va khong bi thay doi.

Flow agent khong expose cac tool cu nhu `search_gym_food` hoac `optimize_meal_plan` cho recommendation, vi cac tool do co the bypass safety/validation. Moi final meal plan phai den tu core engine da validate.

Pham vi y khoa: flow nay chi ho tro quyet dinh cho gym/fitness pho thong. Ket qua khong thay the bac si hoac chuyen gia dinh duong khi user co benh nen, thai ky, roi loan an uong, hoac nhu cau dieu tri.

---

## Luong Du lieu Offline (Data Pipeline)

```
data/raw/vietnam_food_nutrition_data.csv
    |
    v
scripts/collect_foods.py + collect_dishes.py
    | Thu thap va lam sach du lieu
    v
data/processed/foods_full_profile.jsonl
data/processed/dishes_full_profile.jsonl
    |
    v
scripts/build_nutrition_master.py
    | Merge, enrich, standardize
    v
data/processed/nutrition_kb_master.jsonl
    |
    v
scripts/build_qdrant_dataset.py
    | Them: dense_text, sparse_text, diet_tags,
    | allergen_tags, meal readiness, role tags
    v
data/processed/nutrition_kb_qdrant.jsonl
    |
    v
scripts/ingest_v3.py hoac scripts/reindex_qdrant.py
    | Encode embeddings (dense + sparse)
    | Upsert vao Qdrant
    v
Qdrant Collection (blue-green versioned collection)
    |
    v
scripts/cutover_qdrant_alias.py
    | Chuyen alias -> collection moi (blue-green)
    v
gym_food_hybrid_active (alias, hien tro toi gym_food_hybrid_v2_20260426_safetyfix)
```

---

## Caching Strategy

| Lop | Cong nghe | Key | TTL | Muc dich |
|-----|-----------|-----|-----|----------|
| Exact Cache | Redis | SHA-256(payload) | 900s (15 phut) | Cache ket qua nutrition |
| Semantic Cache | Qdrant | Dense vector (cosine >= 0.95) | Vinh vien | Cache cau hoi chat tuong tu |
| Workflow State | Redis | `workflow:{request_id}` | 3600s (1 gio) | Debug/trace workflow |
| LangGraph State | Redis | `thread:{session_id}` | 7 ngay | Memory hoi thoai agent |

---

## Error Handling & Fallbacks

| Buoc | Loi | Fallback |
|------|-----|----------|
| Intent parsing | LLM timeout | Rule-based regex parsing |
| Food retrieval | Qdrant down | Local JSONL index |
| Native rerank | Timeout/crash | Dense + lexical scoring |
| LLM explanation | LLM fail | Deterministic text template |
| SciPy optimizer | No solution | Reduce constraints, retry |

---

## Lien ket

- [NutritionWorkflowService](../services/nutrition-workflow.md)
- [Pipeline RAG](rag-pipeline.md)
- [LangGraph Agent](langgraph-agent.md)
- [Cache & State](../services/cache-state.md)
