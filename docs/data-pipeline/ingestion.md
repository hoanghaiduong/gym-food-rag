# Nhap Du lieu (Ingestion)

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `scripts/ingest_v3.py`, `scripts/reindex_qdrant.py`, `scripts/build_nutrition_master.py`

## Quy trinh Ingest Day du

### Buoc 1: Build Master JSONL

```powershell
cd scripts
python build_nutrition_master.py
```

**Input:**
- `data/processed/foods_full_profile.jsonl`
- `data/processed/dishes_full_profile.jsonl`

**Output:**
- `data/processed/nutrition_kb_master.jsonl` — Tat ca records da merge va enrich
- `data/processed/nutrition_kb_stats.json` — Thong ke

**Xu ly chinh:**
- Map ten truong dinh duong (`NUTRIENT_ALIAS_MAP`): 30+ alias -> 7 truong chuan
- Chuan hoa `energy_kcal`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`
- Goi `enrich_meal_ready_record()`: tinh meal_ready_tier, meal_role_tags, planner_rank_weight
- Dedup theo `entity_id`

### Buoc 2: Build Qdrant Dataset (Optional)

```powershell
python build_qdrant_dataset.py
```

Tao `nutrition_kb_qdrant.jsonl` voi cac truong bo sung: `dense_text`, `sparse_text`, `diet_tags`, `allergen_tags`.

### Buoc 3: Ingest vao Qdrant

```powershell
python ingest_v3.py [options]
```

**CLI Options:**

| Flag | Mac dinh | Mo ta |
|------|----------|-------|
| `--recreate` | false | Xoa collection cu va tao moi |
| `--offset` | 0 | Bo qua N records dau |
| `--limit` | None | Gioi han so records |
| `--batch-size` | 24 | So records moi batch |
| `--collection` | tu settings | Ten collection dich |

**Quy trinh:**

```
1. Doc JSONL records
   |
2. Loc: is_qdrant_ready_record(rec)?
   |-- False -> Skip (ghi log)
   |-- True -> Tiep tuc
   |
3. Build vector payload: build_vector_payload(rec)
   |-- Sinh dense_text (VD: "Uc ga luoc - 165 kcal/100g, protein 31g...")
   |-- Sinh sparse_text
   |-- Lay metadata (energy, protein, tags, etc.)
   |
4. Encode embeddings (BGEEmbeddingService):
   |-- Dense: BGE-M3 encode [dense_text] -> 1024-dim vector
   |-- Sparse: Vietnamese lexical encode [sparse_text] -> sparse vector
   |
5. Tao Qdrant PointStruct:
   |-- id = UUID5(entity_id) — deterministic
   |-- vectors = {"dense": dense_vec, "sparse": sparse_vec}
   |-- payload = metadata dict
   |
6. Upsert batch (24 records/batch)
   |
7. In progress moi batch
```

### Buoc 4: Verify

```powershell
python verify_schema.py
```

Kiem tra collection co du vectors va payload dung schema.

---

## Reindex (Blue-Green Deployment)

```powershell
python reindex_qdrant.py
```

Quy trinh reindex:
1. Doc `COLLECTION_NAME_NEXT` tu `.env`
2. Tao collection moi voi ten do
3. Ingest toan bo du lieu tu JSONL
4. Khong anh huong collection dang active

Sau khi test xong:

```powershell
python cutover_qdrant_alias.py
```

Chuyen alias `gym_food_hybrid_active` sang collection moi.

---

## Ingest V3 Chunked

```powershell
python ingest_v3_chunked.py
```

Phien ban cho du lieu lon — chia thanh nhieu chunk de tranh het memory.

---

## Ingest Legacy (Tham khao)

| Script | Embedding | Search |
|--------|-----------|--------|
| `ingest_data.py` (V1) | Gemini 768d | Dense only |
| `ingest_v2.py` (V2) | BGE-M3 1024d | Dense only |
| `ingest_v3.py` (V3) | BGE-M3 hybrid | Dense + Sparse |

---

## Cau hinh Lien quan

| Bien | Mac dinh | Mo ta |
|------|----------|-------|
| `COLLECTION_NAME` | `gym_food_hybrid_v1` | Collection default |
| `COLLECTION_NAME_ACTIVE` | `""` | Alias dang active |
| `COLLECTION_NAME_NEXT` | `""` | Collection dich khi reindex |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |

---

## Xu ly Loi

| Loi | Giai phap |
|-----|----------|
| Memory error khi encode | Giam `--batch-size` (VD: 8) |
| Qdrant connection refused | Kiem tra docker: `docker logs gym_qdrant` |
| JSONL parse error | Chay `qc_nutrition_kb.py` truoc |
| Encoding cham (CPU) | Dung `ingest_v3_chunked.py` |

---

## Lien ket

- [Tong quan Pipeline](overview.md)
- [Kiem soat chat luong](quality-control.md)
- [Qdrant Collections](../database/qdrant-collections.md)
