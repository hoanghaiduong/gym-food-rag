# Bao Cao Ky Thuat He Thong Gym-Food-RAG

> Cap nhat: 2026-04-28
> Pham vi: backend FastAPI, nutrition recommendation engine, RAG/Qdrant, LangGraph shadow orchestration, evaluation gates.

## 1. Tong Quan

Gym-Food-RAG la backend ho tro quyet dinh dinh duong cho nguoi tap gym/fitness. He thong ket hop tri thuc dinh duong co schema, Qdrant retrieval, tinh toan macro, constraint checking va evaluation de tao thuc don ca nhan hoa.

Pham vi y khoa: he thong chi ho tro goi y bua an pho thong theo macro, allergy va diet constraint. He thong khong thay the bac si hoac chuyen gia dinh duong, dac biet voi nguoi co benh nen, thai ky, roi loan an uong, hoac nhu cau dieu tri.

## 2. Kien Truc Chinh

```text
User
  -> FastAPI V3 API
  -> NutritionWorkflowService
  -> Intent parsing + profile normalization
  -> Macro/TDEE calculation
  -> Qdrant retrieval + local fallback
  -> Candidate filtering/ranking
  -> Deterministic meal planning
  -> Validation and safety policy
  -> Final NutritionRecommendationResponse
```

`NutritionWorkflowService` la core decision engine va la nguon su that duy nhat cho final meal plan. LangGraph khong thay the engine nay.

## 3. LangGraph Shadow Orchestration

Endpoint shadow:

```text
POST /api/v3/nutrition/recommendation-agent
```

LangGraph duoc dung de demo/luan van va orchestration chat, khong tu quyet dinh mon an cuoi. Graph gom cac node:

| Node | Trach nhiem |
|------|-------------|
| `normalize_request` | Chuyen request agent ve `NutritionRecommendationRequest`, tach `session_id`. |
| `clarify_intent` | Hoi lai neu instruction qua mo ho. |
| `run_core_recommendation` | Goi tool an toan `recommend_nutrition_plan_tool`. |
| `inspect_validation` | Chan response neu validation fail hoac co unsafe item. |
| `generate_explanation` | Dien giai plan da validate. |
| `finalize_response` | Tra `NutritionAgentRecommendationResponse` va trace. |

Contract quan trong:

- LangGraph chi goi `recommend_nutrition_plan_tool`.
- Tool nay delegate vao `NutritionWorkflowService.run_main_flow()`.
- Agent khong expose tool `search_gym_food` hoac `optimize_meal_plan` cho final recommendation.
- LLM chi duoc dung de clarify/explain, khong duoc tu tao danh sach mon final.
- Neu core validation fail, agent tra `recommendation=null` va `status=needs_revision`.

## 4. Data va Retrieval

Nguon du lieu runtime:

```text
data/processed/nutrition_kb_master.jsonl
  -> scripts/build_qdrant_dataset.py
  -> data/processed/nutrition_kb_qdrant.jsonl
  -> scripts/ingest_v3_chunked.py
  -> Qdrant versioned collection
  -> alias gym_food_hybrid_active
```

Collection active hien tai:

```text
gym_food_hybrid_active -> gym_food_hybrid_v2_20260426_safetyfix
```

Retrieval runtime dung Qdrant hybrid search, payload policy, role tags, allergen/diet filters, local fallback va validation de dam bao khong tra mon song/unsafe ra final output.

## 5. LLM Backend

De tranh quota/rate-limit trong pre-prod local, cau hinh hien tai nen dung Ollama:

```env
LLM_BACKEND='ollama'
OLLAMA_MODEL='qwen2.5:3b'
NUTRITION_AGENT_MODEL='qwen2.5:3b'
```

Gemini chi nen dung khi co quota on dinh va duoc chon ro trong `.env`. Production gate khong nen phu thuoc vao LLM rewrite de pass retrieval/recommendation safety.

## 6. Redis State va Checkpoint

Redis duoc dung cho:

| Lop | Muc dich |
|-----|----------|
| Exact cache | Cache response nutrition theo payload hash. |
| Workflow state | Luu trace/debug cua core workflow. |
| LangGraph checkpoint | Luu state shadow agent theo `session_id` neu Redis Stack san sang. |

LangGraph checkpoint la optional. Neu Redis/Redis Stack khong san sang, graph fallback ve `checkpoint_backend=none` va endpoint van chay.

## 7. API Chinh

| Endpoint | Vai tro |
|----------|---------|
| `GET /api/v3/nutrition/profile` | Lay profile dinh duong cua user hien tai. |
| `PUT /api/v3/nutrition/profile` | Cap nhat va normalize profile. |
| `POST /api/v3/nutrition/recommendation` | Endpoint production, goi thang core engine. |
| `POST /api/v3/nutrition/recommendation-agent` | Endpoint shadow LangGraph, goi core qua safe tool. |
| `GET /api/v3/nutrition/workflows/{request_id}` | Lay workflow state tu Redis. |
| `POST /api/v3/nutrition/evaluate` | So sanh main flow, pure generation, rule-based baseline. |

## 8. Evaluation va Release Gate

Luong pre-prod chuan:

```powershell
.\myenv\Scripts\python -X utf8 scripts\evaluate_intent_dataset.py
.\myenv\Scripts\python -X utf8 scripts\lint_retrieval_dataset.py
.\myenv\Scripts\python -X utf8 scripts\evaluate_retrieval_dataset.py
.\myenv\Scripts\python -X utf8 scripts\test_nutrition_cases.py
.\myenv\Scripts\python -X utf8 scripts\judge_production_readiness.py
```

Acceptance production:

- Intent KPI pass.
- Retrieval `equivalence_recall_at_20 >= 0.98`.
- Retrieval `required_tag_hit_rate >= 0.98`.
- `forbidden_output_hit_count = 0`.
- `must_exclude_hit_count = 0`.
- `allergy_unsafe_hit_count = 0`.
- Recommendation `case_count >= 50`.
- Recommendation validation and realism pass rate dat nguong judge.
- `unsafe_raw_output_count = 0`.
- `unsafe_label_count = 0`.
- `production_scorecard.json` co verdict `ready_for_pilot`.

## 9. Mapping Voi De Tai

| De tai | Hien thuc |
|--------|-----------|
| Tri thuc dinh duong | Processed KB + payload policy. |
| Qdrant retrieval | `CanonicalKnowledgeService` va alias `gym_food_hybrid_active`. |
| Ollama/Qwen | LLM backend local cho intent/explanation khi cau hinh `LLM_BACKEND=ollama`. |
| LangGraph/LangChain | Shadow orchestration trong `app/services/nutrition/orchestration/`. |
| Constraint checking | Validation trong `NutritionWorkflowService`. |
| Revise/fail-safe | Agent `needs_revision`, core revision rounds va validation gates. |
| Baseline comparison | `nutrition_evaluation_service.evaluate()` va recommendation benchmark. |

## 10. Ket Luan

Huong dung cua du an la giu `NutritionWorkflowService` lam core recommendation engine co rang buoc, con LangGraph la lop orchestration/chat ben ngoai. Cach nay bam dung muc tieu de tai: co RAG, co LLM, co LangGraph, nhung van dam bao final output phai qua retrieval, macro calculation va validation an toan.
