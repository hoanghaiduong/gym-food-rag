# CanonicalKnowledgeService - Truy hoi tri thuc dinh duong

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/nutrition_knowledge_service.py` (~1270 dong)
> **Class chinh:** `CanonicalKnowledgeService`

---

## 1. Tong quan

`CanonicalKnowledgeService` quan ly toan bo lop tri thuc dinh duong cua he thong.
No cung cap:

- **Truy hoi hybrid** (dense + sparse) qua Qdrant vector database
- **Tim kiem local** tren in-memory JSONL index
- **Xay dung payload** chuan hoa cho tung ban ghi thuc pham
- **Reranking** ket qua truy hoi de cai thien do chinh xac

```
             Query (tu workflow)
                    |
         +----------+----------+
         |                     |
    Qdrant Hybrid         Local JSONL
    (dense + sparse)      (in-memory)
         |                     |
         +----------+----------+
                    |
              Rerank + Dedup
                    |
              Candidates List
```

---

## 2. Module-level Functions

### 2.1 `derive_allergen_tags(record) -> list[str]`
Phan tich ten + nhom cua thuc pham de suy ra cac tag di ung:

```python
ALLERGEN_KEYWORDS = {
    "dairy":     ["sua", "pho mai", "milk", "yogurt", "cheese", "whey"],
    "egg":       ["trung", "egg"],
    "soy":       ["dau nanh", "dau hu", "tofu", "soy"],
    "peanut":    ["lac", "dau phong", "peanut"],
    "tree_nut":  ["hat dieu", "hanh nhan", "oc cho", "cashew", "almond"],
    "gluten":    ["wheat", "bread", "pasta", "noodle"],
    "shellfish": ["tom", "cua", "ghe", "oc", "muc", "shrimp", "crab"],
    "fish":      ["ca", "fish", "salmon", "tuna"],
    "sesame":    ["me", "vung", "sesame"],
}
```

Quy trinh:
1. Gom haystack tu `name`, `name_en`, `group_name`, `group`, `aliases`
2. Tao 2 phien ban: raw (Unicode) va normalized (ASCII)
3. Token hoa va so khop voi ALLERGEN_KEYWORDS
4. Tra ve list tags da sap xep va loai trung

### 2.2 `derive_diet_tags(record, allergen_tags?) -> list[str]`
Suy ra diet tags tu thong tin dinh duong va ten:

| Dieu kien                         | Tag          |
|-----------------------------------|--------------|
| protein_g >= 15                   | high_protein |
| fat_g <= 5                        | low_fat      |
| carbs_g >= 20                     | high_carb    |
| Nhom thuc vat + khong co thit     | vegetarian   |
| vegetarian + khong dairy/egg      | vegan        |
| Co ca/hai san + khong co thit do  | pescatarian  |
| Nhom rau/trai cay                 | produce      |

### 2.3 `enrich_meal_ready_record(record) -> dict`
(Tu module `nutrition_record_policy.py`)
Lam giau ban ghi voi cac truong:
- `meal_readiness_score`, `meal_readiness_tier`
- `meal_role_tags`, `meal_role_primary`
- `planner_rank_weight`
- `meal_ready_exclusion_codes`

### 2.4 `build_dense_text(record, allergen_tags, diet_tags) -> str`
Tao van ban day du cho dense embedding:

```
"Mon an: Uc ga / Chicken breast. Nhom: Thit gia cam.
 Taxonomy: protein > poultry. Portion basis: per_100g 100g.
 Nutrients: Energy 165kcal, Protein 31g, Carbohydrate 0g, Fat 3.6g.
 Diet tags: high_protein, low_fat."
```

Bao gom: ten, nhom, taxonomy, portion, nutrients, meal suggestion,
meal roles, ingredient hints, diet/allergen tags, source.

### 2.5 `build_sparse_text(record, allergen_tags, diet_tags) -> str`
Tao van ban token hoa cho sparse embedding:

```
"food | ingredient | v1 | Uc ga | Chicken breast | Thit gia cam |
 high_protein | low_fat | energy 165 | protein 31 | protein:31 | ..."
```

Bao gom: entity_type, granularity, ten, aliases, nhom, taxonomy,
meal hints, diet/allergen tags, nutrient values (nhieu format).

### 2.6 `build_canonical_content(record, allergen_tags, diet_tags) -> str`
Tao noi dung chuan hoa ngan gon cho hien thi:
```
"Thuc pham: Uc ga. Nhom: Thit gia cam.
 Nang luong 165 kcal/100g. Protein 31g, Carb 0g, Fat 3.6g.
 Diet tags: high_protein, low_fat."
```

### 2.7 `build_vector_payload(record) -> dict`
Tao payload day du cho Qdrant, ket hop tat ca cac buoc tren:

```
record --> enrich_meal_ready_record()
       --> derive_allergen_tags()
       --> derive_diet_tags()
       --> build_dense_text()      --> payload["dense_text"]
       --> build_sparse_text()     --> payload["sparse_text"]
       --> build_canonical_content() --> payload["content"]
       --> build_hybrid_text()     --> payload["hybrid_text"]
       --> sanitize_json_payload() --> payload cuoi cung
```

Payload chua ~70 truong bao gom: entity_id, ten, nhom, taxonomy,
macros (energy, protein, carbs, fat, fiber, vitamins, minerals),
meal readiness, diet/allergen tags, image URLs, quality scores, ...

### 2.8 `payload_to_food(payload, score?) -> dict`
Chuyen payload Qdrant thanh dict thuc pham gon nhe cho API response.
Bao gom ~50 truong thuc pham + `retrieval_score`.

---

## 3. Helper Functions

### 3.1 `ascii_normalize(value) -> str`
Chuyen Unicode tieng Viet thanh ASCII lowercase:
`"Uc ga luoc"` -> `"uc ga luoc"`

### 3.2 `raw_normalize(value) -> str`
Lowercase + collapse spaces, giu nguyen Unicode:
`"Uc  Ga  Luoc"` -> `"uc ga luoc"`

### 3.3 `safe_float(value, default) -> float`
Chuyen doi an toan sang float, tra ve default neu None/NaN/Inf.

### 3.4 `sanitize_json_payload(value) -> Any`
Loai bo NaN/Inf khoi dict/list truoc khi luu JSON.

### 3.5 `contains_keyword(raw_text, raw_tokens, normalized_text, tokens, keywords)`
So khop keyword voi ca raw (Unicode) va normalized (ASCII),
ho tro ca single-token va multi-token phrases.

---

## 4. Class CanonicalKnowledgeService

### 4.1 Khoi tao

```python
class CanonicalKnowledgeService:
    def __init__(self, jsonl_path=None):
        self.collection_name = settings.serving_collection_name
        self.jsonl_path = jsonl_path or default_runtime_jsonl_path()
        self.client = QdrantClient(host, port, timeout=30)
        self._embedder = None                    # Lazy load BGEEmbeddingService
        self._records_by_entity_id = None        # Local index by entity_id
        self._records_by_name = None             # Local index by normalized name
```

JSONL path duoc chon theo thu tu uu tien:
1. `nutrition_kb_qdrant.jsonl` (da san sang cho Qdrant)
2. `nutrition_kb_master.jsonl` (master data)
3. `foods_full_profile.jsonl` (raw data)

### 4.2 `retrieve_candidates(queries, limit, ...)` - Method chinh

Day la method truy hoi chinh, su dung **multi-query hybrid search**:

```
queries = ["gain muscle high protein", "thuc pham tang co giau dam", ...]
                    |
    +---------------+---------------+
    |               |               |
  Query 1        Query 2         Query 3
    |               |               |
  Qdrant          Qdrant          Qdrant
  hybrid          hybrid          hybrid
    |               |               |
    +-------+-------+-------+------+
            |               |
         Merge           Dedup
         (best score)    (entity_id)
            |
         Rerank
         (combined query)
            |
         Top-K foods
```

Chi tiet:
1. Voi moi query, goi `_query_points()` voi `rerank=False`
2. Merge ket qua theo entity_id, giu score cao nhat
3. Sap xep theo retrieval_score giam dan
4. Rerank bang combined query (2 query dau)
5. Fallback: neu khong co ket qua, query lai khong filter

Parameters:
- `queries`: list cac cau truy van
- `limit`: so luong ket qua toi da
- `dietary_preference`: loc theo che do an
- `allergy_tags`: loc di ung
- `excluded_foods`: loai bo thuc pham cu the
- `entity_types`: chi lay food/dish
- `dietary_filter`: bat/tat bo loc dietary

### 4.3 `search_local_candidates(query, limit, ...)`
Tim kiem tren local JSONL index:

```python
score = (0.55 * name_overlap
       + 0.20 * exact_match
       + 0.15 * contains_match
       + 0.10 * quality_score)
```

- So khop token overlap giua query va ten thuc pham
- Ho tro exact match va substring match
- Ap dung cac filter: dietary, allergy, excluded
- Dedup theo entity_id va normalized name

### 4.4 `list_local_candidates(limit, ...)`
Liet ke thuc pham tu local index (khong can query):
- Sap xep theo: planner_rank_weight > quality_score > protein_g > energy_kcal
- Ap dung cac filter tuong tu search

### 4.5 `_query_points(query, limit, ...)` - Qdrant hybrid search

```python
# Tao hybrid embedding
hybrid_query = self.embedder.encode_hybrid(query)

# Prefetch ca dense va sparse
prefetch = [
    Prefetch(query=hybrid_query.dense, using="dense", limit=prefetch_limit),
    Prefetch(query=hybrid_query.sparse, using="sparse", limit=prefetch_limit),
]

# Fusion bang RRF (Reciprocal Rank Fusion)
result = self.client.query_points(
    collection_name=...,
    prefetch=prefetch,
    query=FusionQuery(fusion=Fusion.RRF),
    query_filter=filter,
    limit=search_limit,
)
```

### 4.6 `_rerank_points(query, points, limit)`
Rerank ket qua Qdrant:

```
Khi RETRIEVAL_ENABLE_RERANK = True:
final = 0.30 * base + 0.40 * rerank + 0.15 * quality
      + 0.08 * overlap + 0.07 * planner_weight

Khi False:
final = 0.48 * base + 0.22 * quality
      + 0.16 * overlap + 0.14 * planner_weight
```

### 4.7 `_build_filter(dietary_preference, allergy_tags, entity_types)`
Tao Qdrant filter:
- `must`: retrieval_enabled=True, production_retrieval_enabled=True
- `must`: entity_type match (neu co)
- `must`: diet_tags match (vegetarian -> ["vegetarian","vegan"])
- `must_not`: allergen_tags match

### 4.8 `resolve_food_reference(entity_id, food_name, candidate_map, ...)`
Tim thuc pham theo entity_id hoac ten:
1. Tim trong candidate_map (nhanh nhat)
2. Tim theo normalized name trong candidate_map
3. Tim trong local index by entity_id
4. Tim trong local index by name
5. Substring match trong local index
6. Fallback: query Qdrant

### 4.9 `format_candidates_for_prompt(candidates) -> str`
Format danh sach candidates thanh text cho LLM prompt:
```
- entity_id=food_123 | name=Uc ga | type=food | kcal=165.0 |
  protein_g=31.0 | carbs_g=0.0 | fat_g=3.6 | group=Thit gia cam |
  diet_tags=high_protein,low_fat | allergen_tags=none
```

---

## 5. Local Index

### 5.1 `_ensure_local_index()`
Load JSONL file vao memory mot lan (lazy init):
- Doc tung dong, parse JSON
- Neu chua la qdrant-ready -> goi `build_vector_payload()`
- Loai bo records co `qdrant_ingest_eligible=False` hoac
  `production_retrieval_enabled=False`
- Luu vao 2 dict: `_records_by_entity_id` va `_records_by_name`

### 5.2 Cau truc luu tru
```
_records_by_entity_id = {
    "food_001": { payload },
    "food_002": { payload },
    ...
}
_records_by_name = {
    "uc ga": { payload },
    "chicken breast": { payload },
    ...
}
```

---

## 6. Luong du lieu tong the

```
Raw JSONL Data
      |
      v
enrich_meal_ready_record() -- Bo sung meal readiness
      |
      v
derive_allergen_tags()     -- Suy ra di ung
derive_diet_tags()         -- Suy ra diet tags
      |
      v
build_dense_text()         -- Van ban cho dense embedding
build_sparse_text()        -- Token cho sparse embedding
build_canonical_content()  -- Noi dung chuan hoa
      |
      v
build_vector_payload()     -- Payload hoan chinh
      |
      +--------+--------+
      |                 |
   Qdrant            Local JSONL
   (upsert)          (in-memory)
      |                 |
      +--------+--------+
               |
        retrieve_candidates()
               |
           Candidates
```

---

## 7. Lien ket tai lieu

- [NutritionWorkflowService](./nutrition-workflow.md) - Bo dieu phoi su dung service nay
- [BGEEmbeddingService](./embedding-service.md) - Tao embedding cho truy hoi
- [NutritionService](./nutrition-optimizer.md) - Tinh TDEE va toi uu
- [NutritionIntentService](./intent-service.md) - Phan tich y dinh
