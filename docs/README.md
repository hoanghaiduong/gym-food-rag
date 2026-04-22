# Tai lieu Du an Gym Food RAG

> Cap nhat lan cuoi: 2026-04-06

Backend FastAPI cho bai toan **Retrieval-Augmented Generation (RAG) dinh duong** — he thong goi y thuc don ca nhan hoa cho nguoi tap gym, su dung AI de truy xuat va toi uu hoa bua an dua tren ho so suc khoe cua nguoi dung.

---

## Muc luc Tai lieu

### Kien truc He thong
- [Tong quan kien truc](architecture/overview.md) — Tech stack, cac thanh phan chinh, nguyen tac thiet ke
- [Pipeline RAG](architecture/rag-pipeline.md) — Hybrid search (dense + sparse), reranking, retrieval
- [Luong du lieu](architecture/data-flow.md) — End-to-end data flow tu request den response
- [LangGraph Agent V3](architecture/langgraph-agent.md) — Agent hoi thoai voi tool-calling

### Bat dau
- [Huong dan cai dat](getting-started/installation.md) — Cai dat tu A-Z
- [Cau hinh](getting-started/configuration.md) — Tham chieu .env & Settings
- [Chay nhanh](getting-started/quickstart.md) — Chay du an trong 5 phut

### API Reference
- [Tong quan API](api/overview.md) — Versioning, conventions, response format
- [Authentication & RBAC](api/authentication.md) — JWT, refresh token, phan quyen
- [Nutrition V3](api/v3-nutrition.md) — Endpoints goi y dinh duong (core)
- [Chat V3](api/v3-chat.md) — Endpoints chat voi AI agent
- [Auth & Users V3](api/v3-auth-users.md) — Dang ky, dang nhap, quan ly user
- [V2 Legacy](api/v2-legacy.md) — Endpoints V2 (tham khao)

### Services (Business Logic)
- [NutritionWorkflowService](services/nutrition-workflow.md) — Orchestrator chinh (~1800 dong)
- [CanonicalKnowledgeService](services/canonical-knowledge.md) — Hybrid search trong Qdrant
- [BGEEmbeddingService](services/embedding-service.md) — Dense + sparse embeddings
- [NutritionIntentService](services/intent-service.md) — Phan tich y dinh nguoi dung
- [NutritionService](services/nutrition-optimizer.md) — Tinh TDEE + SciPy optimizer
- [OllamaNutritionService](services/llm-service.md) — Multi-backend LLM (Ollama/Gemini)
- [NutritionRecordPolicy](services/record-policy.md) — Quy tac chat luong thuc pham
- [NutritionEvaluationService](services/evaluation-service.md) — A/B testing framework
- [Cache & State](services/cache-state.md) — Redis cache, semantic cache, workflow state

### Co so Du lieu
- [PostgreSQL Schema](database/schema.md) — Tables, relationships, migrations
- [Qdrant Collections](database/qdrant-collections.md) — Vector collections, payload, alias
- [Redis Keys](database/redis-keys.md) — Key patterns, TTL policies

### Data Pipeline
- [Tong quan Pipeline](data-pipeline/overview.md) — CSV -> JSONL -> Qdrant
- [Nhap du lieu](data-pipeline/ingestion.md) — Scripts ingest chi tiet
- [Kiem soat Chat luong](data-pipeline/quality-control.md) — QC & evaluation

### Trien khai
- [Docker Compose](deployment/docker.md) — Cau hinh infrastructure
- [Production](deployment/production.md) — Deploy, monitoring, cutover

### Dong gop
- [Huong dan dong gop](contributing/guidelines.md) — Git workflow, PR process
- [Code Style](contributing/code-style.md) — Conventions, patterns

---

## Tai lieu Hien co Khac

| File | Mo ta |
|------|-------|
| [README.md](../README.md) | Tong quan du an goc |
| [DEBUG_PLAN.md](../DEBUG_PLAN.md) | Ke hoach debug nutrition service |
| [Ops Runbook](nutrition_post_cutover_runbook.md) | Runbook cutover Qdrant alias |
| [OpenAPI Spec](api/api_export.json) | OpenAPI JSON export |
