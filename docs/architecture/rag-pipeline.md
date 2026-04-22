# Pipeline RAG (Retrieval-Augmented Generation)

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/services/embedding_bge_service.py`, `app/services/nutrition_knowledge_service.py`

## Tong quan

Pipeline RAG cua du an su dung **Hybrid Search** — ket hop **dense embedding** (ngu nghia) va **sparse embedding** (tu khoa) — de tim kiem thuc pham chinh xac hon so voi chi dung mot loai. Dac biet toi uu cho **tieng Viet**.

```
User Query
    |
    v
+-------------------+
| Hybrid Encoding   |
| (BGE-M3)          |
| - Dense: 1024-dim |
| - Sparse: lexical |
+-------------------+
    |
    v
+-------------------+     +-------------------+
| Dense Prefetch    |     | Sparse Prefetch   |
| (semantic search) |     | (keyword match)   |
+-------------------+     +-------------------+
    |                         |
    v                         v
+-------------------------------+
| Reciprocal Rank Fusion (RRF)  |
| Ket hop 2 danh sach ket qua  |
+-------------------------------+
    |
    v
+-------------------+
| Reranking         |
| (BGE-M3 native    |
|  hoac fallback)   |
+-------------------+
    |
    v
+-------------------+
| Filter & Dedup    |
| - Diet tags       |
| - Allergen tags   |
| - Exclusion list  |
+-------------------+
    |
    v
Final Candidates
```

---

## Embedding Strategy

### Dense Embedding — BGE-M3

- **Model:** `BAAI/bge-m3` (multilingual, ho tro tot tieng Viet)
- **Chieu:** 1024 dimensions
- **Muc dich:** Tim kiem **ngu nghia** — "uc ga luoc" co the match "thit ga hap" vi cung la protein tu ga
- **Library:** `sentence-transformers` hoac `FlagEmbedding` (native)

### Sparse Embedding — 2 Chien luoc

He thong ho tro 2 chien luoc qua bien `SPARSE_EMBEDDING_STRATEGY`:

#### 1. `bge_m3_native` (Khuyen nghi)
- Su dung `FlagEmbedding.BGEM3FlagModel` de sinh ca dense + sparse cung luc
- Sparse weights la **lexical weights** tu model BGE-M3
- Chinh xac nhat nhung can nhieu RAM/GPU

#### 2. `vi_lexical` (Fallback)
- Dense: `SentenceTransformer("BAAI/bge-m3")`
- Sparse: **Custom `VietnameseLexicalSparseEncoder`**

**VietnameseLexicalSparseEncoder** hoat dong:
1. **Tokenize:** Tach tu tieng Viet bang regex `\w+`
2. **ASCII normalize:** Chuyen dau tieng Viet -> ASCII de match ca 2 dang (`pho` va `pho`)
3. **Loc stopwords:** Bo cac tu khong y nghia: `va`, `cua`, `cho`, `mot`, `nhung`...
4. **Bigrams:** Tao cap tu lien ke: `uc_ga`, `ga_luoc` (neu `SPARSE_USE_BIGRAMS=true`)
5. **Hash:** Dung `blake2b` hash token -> index trong khong gian 2M chieu
6. **TF weighting:** `1.0 + log1p(count)` cho moi token

```python
# Vi du:
text = "uc ga luoc"
tokens = ["uc", "ga", "luoc", "uc_ga", "ga_luoc"]  # + ASCII variants
sparse_vector = SparseVector(indices=[hash1, hash2, ...], values=[1.69, 1.0, ...])
```

### Lua chon Tu dong (`auto`)
Khi `SPARSE_EMBEDDING_STRATEGY="auto"`:
- Neu model la `BAAI/bge-m3` **VA** `FlagEmbedding` import thanh cong -> dung `bge_m3_native`
- Nguoc lai -> fallback ve `vi_lexical`

---

## Hybrid Search trong Qdrant

### Cau truc Query

```python
# Moi query duoc gui den Qdrant voi 2 prefetch:
client.query_points(
    collection_name=collection,
    prefetch=[
        # Nhanh 1: Dense search (ngu nghia)
        Prefetch(query=dense_vector, using="dense", limit=overfetch),
        # Nhanh 2: Sparse search (tu khoa)
        Prefetch(query=sparse_vector, using="sparse", limit=overfetch),
    ],
    # Ket hop 2 nhanh bang RRF
    query=FusionQuery(fusion=Fusion.RRF),
    limit=top_k,
    query_filter=...,  # Diet, allergen filters
)
```

### Reciprocal Rank Fusion (RRF)
RRF ket hop rankings tu 2 nhanh search:
```
score(doc) = sum(1 / (k + rank_i)) for each ranking i
```
- `k` = 60 (mac dinh Qdrant)
- Tai lieu xuat hien o ca 2 nhanh duoc uu tien

### Multi-Query Retrieval
`CanonicalKnowledgeService.retrieve_candidates()` su dung nhieu query dong thoi:
1. **Must-include query**: Tim thuc pham nguoi dung yeu cau cu the (KHONG co diet filter)
2. **Goal-specific queries**: Tu `GOAL_RETRIEVAL_GUIDES` — vi du "high protein foods for muscle gain"
3. **General queries**: Tu khoa chung ve dinh duong

---

## Reranking

### Native Rerank (BGE-M3 Cross-encoder)

Khi `RETRIEVAL_ENABLE_NATIVE_RERANK=true`:
- Chay trong **ProcessPoolExecutor** rieng (tranh block main thread)
- Su dung `BGEM3FlagModel.compute_score()` voi weights: `[dense, sparse, colbert]`
- Mac dinh: `0.4, 0.2, 0.4`
- Gioi han: 6 docs, 512 chars, timeout 25s
- Neu timeout -> tu dong fallback

### Fallback Rerank (Dense + Lexical)

```python
score = 0.75 * cosine_similarity(query_dense, doc_dense)
      + 0.25 * lexical_overlap(query_tokens, doc_tokens)
```

### Blended Strategy
Khi co native rerank cho top-N va fallback cho phan con lai:
```python
# Top-N (native): 80% native + 20% fallback
blended[i] = 0.80 * native_norm[i] + 0.20 * fallback_norm[i]
# Phan con lai: 92% fallback (de thap hon)
blended[j] = 0.92 * fallback_norm[j]
```

---

## Cau hinh Retrieval

| Bien moi truong | Mac dinh | Mo ta |
|-----------------|----------|-------|
| `RETRIEVAL_OVERFETCH_MULTIPLIER` | 4 | Fetch 4x top_k roi loc |
| `RETRIEVAL_PREFETCH_MULTIPLIER` | 2 | Moi nhanh prefetch 2x |
| `RETRIEVAL_ENABLE_RERANK` | true | Bat reranking |
| `RETRIEVAL_ENABLE_NATIVE_RERANK` | false | Bat native BGE-M3 rerank |
| `RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS` | 25 | Timeout native rerank |
| `RETRIEVAL_NATIVE_RERANK_MAX_DOCS` | 6 | So doc toi da native rerank |
| `RETRIEVAL_RERANK_CANDIDATES` | 24 | So ung vien truoc rerank |

---

## So sanh Tien hoa Pipeline

| Phien ban | Embedding | Search | Rerank | Collection |
|-----------|-----------|--------|--------|------------|
| V1 | Gemini `text-embedding-004` (768d) | Dense only | Khong | `gym_food_collection` |
| V2 | BGE-M3 (1024d) | Dense only | Khong | `gym_food_v2` |
| V3 | BGE-M3 hybrid (dense+sparse) | Hybrid (RRF) | Co (native/fallback) | `gym_food_hybrid_v1` + alias |

---

## Lien ket

- [BGEEmbeddingService chi tiet](../services/embedding-service.md)
- [CanonicalKnowledgeService](../services/canonical-knowledge.md)
- [Qdrant Collections](../database/qdrant-collections.md)
- [Kien truc tong quan](overview.md)
