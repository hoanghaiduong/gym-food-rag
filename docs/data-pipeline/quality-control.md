# Kiem soat Chat luong (Quality Control)

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `scripts/qc_nutrition_kb.py`, `scripts/evaluate_retrieval.py`, `scripts/test_nutrition_cases.py`, `scripts/judge_cutover.py`

## Tong quan

He thong QC hoat dong o 3 cap:
1. **Data QC** — Kiem tra du lieu JSONL truoc khi ingest
2. **Retrieval Evaluation** — Danh gia chat luong hybrid search
3. **End-to-end Testing** — Test full recommendation pipeline

---

## 1. Data QC (`qc_nutrition_kb.py`)

```powershell
cd scripts
python qc_nutrition_kb.py
```

**Input:** `data/processed/nutrition_kb_master.jsonl`

**Output:**
- `data/processed/nutrition_kb_qc_flags.jsonl` — Chi tiet tung van de
- `data/processed/nutrition_kb_qc_summary.json` — Thong ke tong hop

### Cac Rule Kiem tra

| Code | Severity | Mo ta |
|------|----------|-------|
| `missing_entity_id` | error | Thieu entity_id |
| `missing_name` | error | Thieu ten thuc pham |
| `missing_energy` | warning | Thieu thong tin calo |
| `extreme_energy` | warning | Calo > 900 kcal/100g |
| `macro_exceeds_energy` | warning | Tong macro vuot calo (kiem tra consistency) |
| `missing_group` | info | Thieu nhom thuc pham |
| `qdrant_excluded_by_policy` | warning | Khong du dieu kien nhap Qdrant |

### QC Policy (`nutrition_qc_policy.py`)

Policy duoc danh gia qua `evaluate_qc_policy()`:
- Kiem tra `meal_ready_tier` (blocked = khong ingest)
- Kiem tra `qdrant_ingest_eligible`
- Kiem tra `retrieval_enabled`
- Liet ke `qdrant_exclusion_reasons`

---

## 2. Retrieval Evaluation (`evaluate_retrieval.py`)

```powershell
python evaluate_retrieval.py
```

Danh gia chat luong hybrid search bang cac test queries:
- Do chinh xac retrieval (recall@k)
- So sanh dense vs sparse vs hybrid
- Kiem tra reranking hieu qua

---

## 3. End-to-end Testing

### Test Nutrition Cases

```powershell
python test_nutrition_cases.py \
  --username "admin" \
  --password "admin" \
  --recommendation-timeout 900 \
  --heartbeat-seconds 10
```

Chay nhieu test cases qua API:
- Goi y 3 bua cho nguoi tang co
- Goi y 4 bua cho nguoi giam can
- Goi y voi di ung (hai san, sua)
- Goi y voi che do an (vegetarian, pescatarian)
- Goi y voi must_include va excluded_foods

**Output:** `logs/nutrition_test_results.jsonl`

### Judge Cutover

```powershell
python judge_cutover.py \
  --max-response-time-seconds 240 \
  --max-discouraged-items 1
```

Phan tich ket qua test va quyet dinh co nen cutover:
- Kiem tra thoi gian response
- Kiem tra so luong "discouraged items" (thuc pham khong phu hop)
- Pass/Fail verdict

---

## 4. A/B Evaluation (Trong API)

API endpoint `/api/v3/nutrition/evaluate` chay 3 phuong an dong thoi:

| Variant | Mo ta | Diem manh |
|---------|-------|-----------|
| `main_flow` | Full pipeline (intent + RAG + SciPy + LLM) | Chinh xac nhat |
| `pure_generation` | LLM tu sinh thuc don (khong SciPy) | Nhanh nhat |
| `rule_based` | Rule-based selection + SciPy | Don gian nhat |

### Tieu chi So sanh

1. **Pass/Fail** — Validation co dat khong?
2. **Violation rate** — Ti le vi pham (di ung, diet)
3. **Calorie error %** — Sai so calo
4. **Macro deviation %** — Sai so macro
5. **Response time** — Thoi gian xu ly

**Output:** `logs/nutrition_evaluations.jsonl`

---

## 5. Cac Script Kiem tra Khac

| Script | Muc dich |
|--------|----------|
| `verify_schema.py` | Verify Qdrant collection co dung schema |
| `check_native_rerank.py` | Test native BGE-M3 reranking |
| `ollama_smoke.py` | Smoke test ket noi Ollama |
| `run_and_verify.py` | Chay tat ca va verify |

---

## Quy trinh QC Khuyen nghi

```
1. build_nutrition_master.py     # Merge du lieu
2. qc_nutrition_kb.py            # QC du lieu
   |-- Xem qc_flags.jsonl       # Sua loi
   |-- Lap lai neu can
3. build_qdrant_dataset.py       # Chuan bi Qdrant data
4. ingest_v3.py                  # Ingest
5. verify_schema.py              # Verify collection
6. test_nutrition_cases.py       # Test E2E
7. judge_cutover.py              # Quyet dinh cutover
8. cutover_qdrant_alias.py       # Cutover neu dat
```

---

## Lien ket

- [Tong quan Pipeline](overview.md)
- [Nhap du lieu](ingestion.md)
- [NutritionRecordPolicy](../services/record-policy.md)
- [NutritionEvaluationService](../services/evaluation-service.md)
