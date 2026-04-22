# Qdrant Collections

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/services/nutrition_knowledge_service.py`, `scripts/reindex_qdrant.py`, `scripts/ingest_v3.py`

## Tong quan

Qdrant la **vector database** chinh cua he thong, luu tru embeddings thuc pham de phuc vu hybrid search. He thong su dung **alias-based blue-green deployment** de chuyen doi collection khong downtime.

---

## Collection Chinh: Nutrition Knowledge Base

### Cau hinh Collection

| Thuoc tinh | Gia tri |
|-----------|---------|
| **Ten collection** | `gym_food_hybrid_v1` (hoac `vN_YYYYMMDD`) |
| **Alias** | `gym_food_hybrid_active` |
| **So vectors** | ~500-1000 (tuy du lieu) |

### Vector Spaces

| Named Vector | Kieu | Chieu | Distance | Mo ta |
|-------------|------|-------|----------|-------|
| `dense` | Dense | 1024 | Cosine | BGE-M3 semantic embedding |
| `sparse` | Sparse | ~2M | Dot product | Vietnamese lexical hashing |

### Payload Schema

Moi point trong Qdrant co payload voi cac truong sau:

| Truong | Kieu | Vi du | Mo ta |
|--------|------|-------|-------|
| `entity_id` | str | `"food_001"` | ID thuc pham |
| `entity_type` | str | `"food"` / `"dish"` | Loai: nguyen lieu hay mon an |
| `granularity` | str | `"ingredient"` / `"dish"` | Muc do chi tiet |
| `name` | str | `"Uc ga luoc"` | Ten tieng Viet |
| `name_en` | str | `"Boiled chicken breast"` | Ten tieng Anh |
| `group_name` | str | `"Thit gia cam"` | Nhom thuc pham |
| `energy_kcal` | float | `165.0` | Nang luong (kcal/100g) |
| `protein_g` | float | `31.0` | Protein (g/100g) |
| `carbs_g` | float | `0.0` | Carbohydrate (g/100g) |
| `fat_g` | float | `3.6` | Chat beo (g/100g) |
| `fiber_g` | float | `0.0` | Chat xo (g/100g) |
| `portion_basis` | str | `"per_100g"` | Don vi tinh |
| `portion_g` | float | `100.0` | Khoi luong 1 phan |
| `diet_tags` | list[str] | `["low_fat","high_protein"]` | Tags che do an |
| `allergen_tags` | list[str] | `["poultry"]` | Tags di ung |
| `meal_suggestion` | str | `"Breakfast,Lunch"` | Bua an phu hop |
| `meal_ready_tier` | str | `"ready"` / `"partial"` | Muc do san sang lam bua an |
| `meal_role_tags` | list[str] | `["protein_anchor"]` | Vai tro trong bua an |
| `planner_rank_weight` | float | `0.85` | Trong so xep hang |
| `image_url` | str | `/assets/nutrition_images/...` | URL hinh anh |
| `content` | str | `"Uc ga luoc - 165 kcal..."` | Text de hien thi |
| `dense_text` | str | (long form) | Text dung de tao dense embedding |
| `sparse_text` | str | (keyword-rich) | Text dung de tao sparse embedding |

### Filter Indexes

Qdrant tu dong index cac truong thuong dung cho filtering:
- `diet_tags` — Loc theo che do an (vegetarian, vegan, pescatarian)
- `allergen_tags` — Loai tru di ung (dairy, egg, shellfish)
- `meal_ready_tier` — Chi lay mon "ready" hoac "partial"
- `entity_type` — Loc food vs dish

---

## Alias Management

### Cach Hoat dong

```
gym_food_hybrid_v1  <---- gym_food_hybrid_active (alias)
gym_food_hybrid_v2  (standby)
```

- App luon query qua **alias** `gym_food_hybrid_active` (`COLLECTION_NAME_ACTIVE`)
- Khi reindex, tao collection moi, ingest, roi chuyen alias (blue-green)
- Rollback = chuyen alias ve collection cu

### Bien moi truong

| Bien | Muc dich | Vi du |
|------|----------|-------|
| `COLLECTION_NAME` | Fallback/default | `gym_food_hybrid_v1` |
| `COLLECTION_NAME_ACTIVE` | Alias dang dung | `gym_food_hybrid_active` |
| `COLLECTION_NAME_NEXT` | Collection dang reindex | `gym_food_hybrid_v2_20260401` |

### Logic chon Collection

```python
# app/core/config.py
@property
def serving_collection_name(self) -> str:
    return self.COLLECTION_NAME_ACTIVE or self.COLLECTION_NAME

@property
def reindex_target_collection_name(self) -> str:
    return self.COLLECTION_NAME_NEXT or self.COLLECTION_NAME
```

---

## Semantic Cache Collection

Ngoai knowledge base, Qdrant cung duoc dung cho **semantic cache** (trong Chat V3):

| Thuoc tinh | Gia tri |
|-----------|---------|
| Collection | `chat_cache_v1` (hoac tuong tu) |
| Vector | Dense only (1024d) |
| Threshold | cosine >= 0.95 |
| Payload | `question`, `answer`, `created_at` |

---

## Quy trinh Reindex

```
1. Set COLLECTION_NAME_NEXT="gym_food_hybrid_vN_YYYYMMDD"
2. Chay: python scripts/reindex_qdrant.py
   -> Tao collection moi
   -> Doc JSONL master -> encode embeddings -> upsert
3. Test voi collection moi
4. Chay: python scripts/cutover_qdrant_alias.py
   -> Chuyen alias sang collection moi
5. Set COLLECTION_NAME_NEXT=""
```

> Chi tiet: [Ops Runbook](../nutrition_post_cutover_runbook.md)

---

## Lien ket

- [Pipeline RAG](../architecture/rag-pipeline.md)
- [Data Pipeline](../data-pipeline/overview.md)
- [CanonicalKnowledgeService](../services/canonical-knowledge.md)
