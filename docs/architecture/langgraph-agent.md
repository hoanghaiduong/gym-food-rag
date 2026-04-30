# LangGraph Nutrition Orchestration

> Cap nhat lan cuoi: 2026-04-28
> Source code: `app/services/nutrition/orchestration/`, `app/api/v3/nutrition.py`

## Tong quan

LangGraph trong du an la **orchestration/chat layer** cho bai toan ho tro quyet dinh dinh duong. LangGraph khong tu quyet dinh mon an cuoi cung. Moi final meal plan phai den tu `NutritionWorkflowService`, engine co retrieval, toi uu macro va validation an toan.

Endpoint production on dinh van la:

```text
POST /api/v3/nutrition/recommendation
```

Endpoint LangGraph shadow/de tai la:

```text
POST /api/v3/nutrition/recommendation-agent
```

## Kien truc

```text
User
  -> FastAPI shadow endpoint
  -> LangGraph orchestration
  -> recommend_nutrition_plan_tool
  -> NutritionWorkflowService
  -> Qdrant + Redis + Ollama/Gemini explanation fallback
  -> Validation
  -> LangGraph finalize response
```

## Cac node

| Node | Vai tro |
|------|---------|
| `normalize_request` | Chuyen request agent ve `NutritionRecommendationRequest` core, tach `session_id` khoi cache key. |
| `clarify_intent` | Hoi lai neu instruction qua mo ho; neu can hoi lai thi khong goi core engine. |
| `run_core_recommendation` | Chi goi `recommend_nutrition_plan_tool`, tool nay delegate vao `NutritionWorkflowService.run_main_flow()`. |
| `inspect_validation` | Doc validation cua core; neu fail hoac co unsafe output thi khong tra final plan. |
| `generate_explanation` | Tao cau tra loi tu plan da validate; LLM chi duoc dung o lop dien giai/hop thoai. |
| `finalize_response` | Tra `NutritionAgentRecommendationResponse` voi trace cua graph. |

## Safety contract

- LangGraph khong expose tool `search_gym_food` va `optimize_meal_plan` cho luong recommendation-agent.
- LLM khong duoc tu lap danh sach mon an cuoi.
- Neu `validation.passed=false`, response agent co `recommendation=null`.
- Neu bat ky item co `final_output_allowed=false` hoac `consumption_state=requires_preparation`, agent chan final plan.
- User-facing label phai di qua `safe_display_name` trong core response.

## Mapping voi de cuong luan van

| Thanh phan de cuong | Hien thuc trong code |
|---------------------|----------------------|
| Tri thuc dinh duong co schema | `data/processed/nutrition_kb_master.jsonl`, payload policy, schemas nutrition. |
| Truy hoi ngu nghia Qdrant | `CanonicalKnowledgeService`, active alias `gym_food_hybrid_active`. |
| Redis cache/state | `redis_state_service`, exact cache, workflow state, optional LangGraph checkpoint. |
| Mo hinh tao sinh Ollama/Qwen | `OLLAMA_MODEL`, explanation/intent layer; core validation khong phu thuoc LLM de quyet dinh an toan. |
| LangChain/LangGraph orchestration | `app/services/nutrition/orchestration/`. |
| Constraint checking/revise | `NutritionWorkflowService` validation + agent `needs_revision` guard. |
| So sanh baseline | `nutrition_evaluation_service.evaluate()` voi main flow, pure generation, rule-based. |

## Luu y van hanh

- `NUTRITION_AGENT_ENABLED=true` bat endpoint shadow.
- `NUTRITION_AGENT_MODEL` mac dinh theo `OLLAMA_MODEL`.
- `NUTRITION_AGENT_REDIS_CHECKPOINT=true` cho phep LangGraph dung Redis checkpoint neu Redis san sang; neu Redis khong san sang, graph van chay khong checkpoint.
- Endpoint shadow khong thay the production gate; moi release van phai pass `judge_production_readiness.py`.

## Pham vi y khoa

He thong la cong cu ho tro quyet dinh cho gym/fitness pho thong, giup goi y bua an theo macro, allergy/diet constraint va du lieu dinh duong co san. He thong khong thay the chan doan, dieu tri, hoac tu van ca nhan tu bac si/chuyen gia dinh duong, dac biet voi nguoi co benh nen, thai ky, roi loan an uong, hoac yeu cau y khoa dac thu.
