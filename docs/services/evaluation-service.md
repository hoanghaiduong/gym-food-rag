# Nutrition Evaluation Service - Dich vu A/B Testing dinh duong

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/nutrition_evaluation_service.py`

---

## Tong quan

`NutritionEvaluationService` thuc hien **A/B testing tu dong** giua 3 phuong phap tao
thuc don dinh duong. Muc dich la so sanh chat luong dau ra cua cac variant khac nhau
de xac dinh phuong phap nao cho ket qua tot nhat voi tung request cu the.

Service nay duoc truy cap qua API endpoint:

```
POST /api/v3/nutrition/evaluate
```

---

## 1. Kien truc

### 1.1 Khoi tao

```python
class NutritionEvaluationService:
    def __init__(self):
        self.workflow = nutrition_workflow_service
        self.log_path = LOGS_DIR / "nutrition_evaluations.jsonl"
```

- Phu thuoc vao `nutrition_workflow_service` de goi cac variant.
- Log file: `logs/nutrition_evaluations.jsonl` (JSON Lines format).

### 1.2 Singleton instance

```python
nutrition_evaluation_service = NutritionEvaluationService()
```

Module-level singleton, import truc tiep:
```python
from app.services.nutrition_evaluation_service import nutrition_evaluation_service
```

---

## 2. Ba variant duoc so sanh

### 2.1 Variant 1: main_flow

```python
main_result = self.workflow.run_main_flow(current_user, baseline_request)
```

- **Mo ta:** Luong chinh cua he thong (production flow).
- **Pipeline:** Retrieve -> Deterministic Optimize -> Validate -> Explain
- **Dac diem:** Co revise loop (so lan revision duoc ghi nhan).
- **Notes:** `"retrieve -> deterministic optimize -> validate -> explain"`, kem thong tin `revisions_used`.

### 2.2 Variant 2: pure_generation

```python
pure_result = self.workflow.run_pure_generation_baseline(profile, baseline_request, targets)
```

- **Mo ta:** Chi dung LLM, khong retrieval, khong revise loop.
- **Pipeline:** LLM sinh toan bo thuc don tu dau.
- **Notes:** `"LLM only, no retrieval, no revise loop"`

### 2.3 Variant 3: rule_based

```python
rule_result = self.workflow.run_rule_based_baseline(profile, baseline_request, targets, candidates)
```

- **Mo ta:** Dung TDEE + macro targets + lua chon tinh tu danh sach thuc pham da retrieve.
- **Pipeline:** Tinh TDEE -> Xac dinh macro targets -> Chon mon an tinh tu candidates.
- **Notes:** `"TDEE + macro targets + static meal selection from retrieved foods"`

---

## 3. Quy trinh evaluate

### 3.1 Ham evaluate(current_user, request)

Day la ham entry-point chinh. Quy trinh chay:

**Buoc 1 - Chuan bi:**
```python
profile = self.workflow.build_profile(current_user)
baseline_request = request.model_copy(update={"use_cache": False, "include_debug": False})
targets = self.workflow._compute_targets(profile, baseline_request)
candidates = self.workflow._retrieve_candidates(profile, baseline_request, targets)
```

- Tat cache (`use_cache=False`) de dam bao moi variant chay that.
- Tat debug info (`include_debug=False`) de giam nhieu.
- Tinh `targets` (TDEE, macro goals) va `candidates` (danh sach thuc pham) mot lan duy nhat,
  dung chung cho cac variant can.

**Buoc 2 - Chay 3 variant:**

Moi variant tra ve ket qua bao gom:
- `response_time_seconds`: Thoi gian xu ly
- `validation`: Ket qua kiem tra (totals, calorie error, macro deviation, v.v.)
- Cac truong bo sung tuy variant (vd: `revisions_used` cho main_flow)

**Buoc 3 - So sanh va chon best_variant:**

```python
best_variant = min(variants, key=lambda item: (
    0 if item["passed"] else 1,       # Uu tien: pass truoc
    item["violation_rate"],            # Roi: ty le vi pham thap
    item["calorie_error_pct"],         # Roi: sai so calorie thap
    item["macro_deviation_pct"],       # Cuoi: lech macro thap
))["name"]
```

**Buoc 4 - Ghi log va tra ve ket qua.**

### 3.2 Thu tu uu tien so sanh

He thong so sanh 4 chi so theo thu tu uu tien giam dan:

| Thu tu | Chi so | Y nghia | Tot hon khi |
|--------|--------|---------|-------------|
| 1 | `passed` | Ket qua co dat chuan khong | `True` (= 0) |
| 2 | `violation_rate` | Ty le vi pham cac rang buoc | Thap hon |
| 3 | `calorie_error_pct` | Sai so calorie so voi target (%) | Thap hon |
| 4 | `macro_deviation_pct` | Do lech macro so voi target (%) | Thap hon |

Noi cach khac:
- Mot variant `passed=True` luon thang variant `passed=False`.
- Neu ca hai deu pass (hoac deu fail), so sanh `violation_rate`.
- Neu bang nhau, tiep tuc so `calorie_error_pct`, roi `macro_deviation_pct`.

---

## 4. Cau truc du lieu tra ve

### 4.1 _variant_summary()

Moi variant duoc tom tat thanh mot dict thong nhat:

```python
{
    "name": "main_flow",              # Ten variant
    "response_time_seconds": 2.345,   # Thoi gian xu ly
    "totals": {...},                  # Tong calories, protein, carbs, fat
    "calorie_error_kcal": 45.0,       # Sai so calorie (kcal)
    "calorie_error_pct": 2.1,         # Sai so calorie (%)
    "macro_deviation_pct": 3.5,       # Do lech macro (%)
    "violation_rate": 0.0,            # Ty le vi pham
    "passed": True,                   # Dat chuan hay khong
    "notes": [...]                    # Ghi chu bo sung
}
```

### 4.2 Response payload day du

```python
{
    "request_id": "uuid-...",
    "created_at": "2026-04-06T10:30:00+00:00",
    "profile": {...},                 # Thong tin nguoi dung (tuoi, can nang, ...)
    "targets": {
        "tdee": 2200,
        "calorie_tolerance_pct": 5,
        "macro_tolerance_pct": 10,
        ...
    },
    "variants": [
        {...},  # main_flow
        {...},  # pure_generation
        {...},  # rule_based
    ],
    "best_variant": "main_flow",      # Ten variant tot nhat
    "log_path": "logs/nutrition_evaluations.jsonl"
}
```

---

## 5. Logging

### 5.1 File log

- Duong dan: `logs/nutrition_evaluations.jsonl`
- Format: JSON Lines (moi dong la mot JSON object hoan chinh)
- Thu muc `logs/` duoc tu dong tao neu chua co (`LOGS_DIR.mkdir(parents=True, exist_ok=True)`)
- Encoding: UTF-8, `ensure_ascii=False` (ho tro tieng Viet)

### 5.2 Noi dung log

Moi lan goi `evaluate()`, toan bo `response_payload` duoc append vao file, bao gom:
- Thong tin profile nguoi dung
- Targets (TDEE, calorie tolerance, macro tolerance)
- Ket qua chi tiet cua ca 3 variant
- Ten variant tot nhat

### 5.3 Muc dich log

- **Phan tich offline:** So sanh hieu suat cac variant theo thoi gian.
- **Debug:** Khi ket qua thuc don khong nhu mong doi, kiem tra log de hieu tai sao.
- **Tinh chinh:** Du lieu giup dieu chinh cac nguong (tolerance) va trong so cua tung phuong phap.

---

## 6. API Endpoint

```
POST /api/v3/nutrition/evaluate
```

### Request

Su dung schema `NutritionRecommendationRequest` (giong API tao thuc don chinh),
nhung hai truong se bi override:

| Truong | Gia tri ghi de | Ly do |
|--------|----------------|-------|
| `use_cache` | `False` | Dam bao chay that, khong lay tu cache |
| `include_debug` | `False` | Giam nhieu trong ket qua |

### Response

Tra ve object `response_payload` nhu mo ta o phan 4.2. Endpoint nay **chay 3 variant**
nen mat nhieu thoi gian hon API thuong. Nen su dung cho **testing/benchmarking** only.

---

## 7. Luu y thiet ke

- **Cong bang:** Ca 3 variant dung chung `profile`, `targets`, `candidates`.
- **Khong anh huong production:** `use_cache=False` dam bao khong ghi de cache.
- **Log append-only:** File log chi append, khong bao gio xoa du lieu cu.

---

## 8. Benchmark so sanh cho luan van

Khi can chay so sanh tren nhieu case, dung CLI rieng thay vi goi endpoint `/evaluate`
lap lai nhieu lan:

```powershell
.\myenv\Scripts\python -X utf8 scripts\compare_nutrition_baselines.py
```

CLI nay chay cung 3 variant (`main_flow`, `pure_generation`, `rule_based`) tren bo
recommendation production cases, nhung chi ghi artifact nghien cuu vao:

```text
logs/nutrition_case_runs/_debug/comparison/latest/comparison_summary.json
```

Mac dinh CLI chi sinh 1 file summary, khong ghi vao canonical root va khong tham gia
`judge_production_readiness.py`. Per-case JSON va Markdown report chi duoc ghi khi bat
co `--emit-case-files` hoac `--emit-markdown`.

Voi run dai de gap loi Gemini `429/503`, co the resume bang summary da ghi tang dan:

```powershell
.\myenv\Scripts\python -X utf8 scripts\compare_nutrition_baselines.py --run-name thesis_full --emit-markdown --resume
```

Neu can bo qua cac case dau da co log rieng, dung production case index 1-based:

```powershell
.\myenv\Scripts\python -X utf8 scripts\compare_nutrition_baselines.py --run-name thesis_full_part2 --start-index 6 --emit-markdown
```

---

## Tai lieu lien quan

- [Tong quan kien truc](../architecture/overview.md)
- [RAG Pipeline](../architecture/rag-pipeline.md)
- [LLM Service](./llm-service.md)
- [Record Policy](./record-policy.md)
- [Cache va State Management](./cache-state.md)
