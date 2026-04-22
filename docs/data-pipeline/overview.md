# Tong quan Data Pipeline

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `scripts/` directory

## Tong quan

Data pipeline chuyen hoa du lieu dinh duong tu **CSV goc** thanh **vector embeddings** trong Qdrant, di qua nhieu giai doan lam sach, merge, enrichment va QC.

```
[Thu thap du lieu]
    |
    v
data/raw/vietnam_food_nutrition_data.csv
    |
    v
[Thu thap chi tiet]
scripts/collect_foods.py     -> data/processed/foods_full_profile.jsonl
scripts/collect_dishes.py    -> data/processed/dishes_full_profile.jsonl
    |
    v
[Merge & Enrich]
scripts/build_nutrition_master.py -> data/processed/nutrition_kb_master.jsonl
                                    data/processed/nutrition_kb_stats.json
    |
    v
[Quality Control]
scripts/qc_nutrition_kb.py   -> data/processed/nutrition_kb_qc_flags.jsonl
                                data/processed/nutrition_kb_qc_summary.json
    |
    v
[Build Qdrant Dataset]
scripts/build_qdrant_dataset.py -> data/processed/nutrition_kb_qdrant.jsonl
    |
    v
[Ingest vao Qdrant]
scripts/ingest_v3.py         -> Qdrant collection (gym_food_hybrid_vN)
    |
    v
[Cutover Alias]
scripts/cutover_qdrant_alias.py -> gym_food_hybrid_active (alias)
```

---

## Cac Giai doan Chi tiet

### Giai doan 1: Thu thap Du lieu Goc

| Script | Input | Output | Mo ta |
|--------|-------|--------|-------|
| `data_collector.py` | Web sources | `data/raw/vietnam_food_*.csv` | Thu thap tu khoa va lien ket |
| `data_collector_v2.py` | Web sources | `data/raw/` | Phien ban nang cap |

### Giai doan 2: Thu thap Chi tiet (Full Profile)

| Script | Input | Output | Mo ta |
|--------|-------|--------|-------|
| `collect_foods.py` | Raw data | `data/processed/foods_full_profile.jsonl` | Profile day du cho tung thuc pham |
| `collect_dishes.py` | Raw data | `data/processed/dishes_full_profile.jsonl` | Profile day du cho tung mon an |
| `collector_common.py` | — | — | Utility chung cho collectors |

### Giai doan 3: Merge & Enrich

**Script:** `build_nutrition_master.py`

1. Doc `foods_full_profile.jsonl` + `dishes_full_profile.jsonl`
2. Chuan hoa ten truong dinh duong qua `NUTRIENT_ALIAS_MAP`:
   - `"Nang luong"` -> `energy_kcal`
   - `"Chat dam"` -> `protein_g`
   - `"Chat beo"` -> `fat_g`
   - `"Glucid"` -> `carbs_g`
3. Enrich voi `enrich_meal_ready_record()` tu `NutritionRecordPolicy`
4. Output: `nutrition_kb_master.jsonl` + statistics

### Giai doan 4: Quality Control

**Script:** `qc_nutrition_kb.py`

Kiem tra tung record:
- Thieu truong bat buoc (entity_id, name, energy_kcal)
- Gia tri dinh duong bat thuong (energy > 900 kcal/100g)
- Tong macro vuot qua nang luong
- Du lieu khong du dieu kien nhap Qdrant

Output: `nutrition_kb_qc_flags.jsonl` (danh sach van de) + `nutrition_kb_qc_summary.json`

### Giai doan 5: Build Qdrant Dataset

**Script:** `build_qdrant_dataset.py`

1. Doc `nutrition_kb_master.jsonl`
2. Tao `dense_text` va `sparse_text` cho moi record
3. Them: `diet_tags`, `allergen_tags`, `meal_role_tags`, `meal_ready_tier`
4. Output: `nutrition_kb_qdrant.jsonl` (san sang cho ingest)

### Giai doan 6: Ingest vao Qdrant

**Script:** `ingest_v3.py`

1. Doc `nutrition_kb_qdrant.jsonl`
2. Encode embeddings (dense + sparse) bang `BGEEmbeddingService`
3. Tao/recreate collection voi 2 named vectors (dense + sparse)
4. Upsert theo batch (BATCH_SIZE = 24)
5. Point ID = UUID5 tu entity_id (deterministic)

### Giai doan 7: Cutover Alias

**Script:** `cutover_qdrant_alias.py`

Chuyen alias `gym_food_hybrid_active` tu collection cu sang collection moi.

---

## Danh sach Tat ca Scripts

| Script | Muc dich |
|--------|----------|
| `collect_foods.py` | Thu thap thuc pham nguyen lieu |
| `collect_dishes.py` | Thu thap mon an che bien |
| `collector_common.py` | Utilities chung cho collectors |
| `data_collector.py` | Data collector V1 |
| `data_collector_v2.py` | Data collector V2 |
| `build_nutrition_master.py` | Merge + enrich -> master JSONL |
| `build_qdrant_dataset.py` | Chuan bi du lieu cho Qdrant |
| `qc_nutrition_kb.py` | Kiem tra chat luong du lieu |
| `nutrition_qc_policy.py` | QC policy rules |
| `nutrition_payload_utils.py` | Utility xu ly payload |
| `ingest_v3.py` | Ingest vao Qdrant (V3 hybrid) |
| `ingest_v3_chunked.py` | Ingest chunked (du lieu lon) |
| `ingest_v2.py` | Ingest V2 (dense only, legacy) |
| `ingest_data.py` | Ingest V1 (legacy) |
| `reindex_qdrant.py` | Reindex full collection |
| `cutover_qdrant_alias.py` | Chuyen alias Qdrant |
| `sync_nutrition_images.py` | Dong bo hinh anh thuc pham |
| `evaluate_retrieval.py` | Danh gia chat luong retrieval |
| `test_nutrition_cases.py` | Test cases dinh duong |
| `judge_cutover.py` | Danh gia sau cutover |
| `check_native_rerank.py` | Kiem tra native rerank |
| `verify_schema.py` | Verify Qdrant schema |
| `export_openapi.py` | Export OpenAPI spec |
| `debug_import.py` | Debug import issues |
| `ollama_smoke.py` | Test ket noi Ollama |
| `run_and_verify.py` | Chay va verify het |

---

## Lien ket

- [Nhap du lieu chi tiet](ingestion.md)
- [Kiem soat chat luong](quality-control.md)
- [Qdrant Collections](../database/qdrant-collections.md)
