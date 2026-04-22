# BGEEmbeddingService - Hybrid Embedding va Reranking

> **Cap nhat:** 2026-04-06
> **Source code:** `app/services/embedding_bge_service.py` (~449 dong)
> **Factory:** `app/services/embedding_factory.py` (~125 dong)
> **Class chinh:** `BGEEmbeddingService`, `VietnameseLexicalSparseEncoder`

---

## 1. Tong quan

He thong embedding cung cap kha nang **hybrid search** (ket hop dense va sparse)
cho truy hoi thuc pham tu Qdrant. Co 2 chien luoc sparse embedding va
mot he thong reranking linh hoat.

```
             Input Text
                |
        +-------+-------+
        |               |
   Dense Vector    Sparse Vector
   (BGE-M3 /       (Native BGE-M3
    SentenceTransf)  hoac Vi Lexical)
        |               |
        v               v
     HybridEmbedding
     {
       dense:  [0.12, -0.05, ...] (1024 dims)
       sparse: {indices: [...], values: [...]}
     }
```

---

## 2. Kien truc tong the

### 2.1 Hai chien luoc sparse

| Chien luoc        | Mo ta                                    | Khi nao dung                        |
|-------------------|------------------------------------------|-------------------------------------|
| `bge_m3_native`   | Dung FlagEmbedding BGEM3FlagModel        | Khi FlagEmbedding co san            |
| `vi_lexical`      | VietnameseLexicalSparseEncoder (hashing) | Fallback khi khong co FlagEmbedding |

### 2.2 Chon chien luoc

```python
if strategy == "auto":
    if model == "BAAI/bge-m3" and FlagEmbedding available:
        -> "bge_m3_native"     # Dense + Sparse tu cung 1 model
    else:
        -> "vi_lexical"        # Dense: SentenceTransformer, Sparse: lexical hash
else:
    -> use requested strategy
```

Cau hinh qua env vars:
- `SPARSE_EMBEDDING_STRATEGY`: "auto" (default), "bge_m3_native", "vi_lexical"
- `LOCAL_EMBEDDING_MODEL` hoac `V2_EMBEDDING_MODEL`: ten model (default "BAAI/bge-m3")

---

## 3. SparseVector va HybridEmbedding Dataclasses

```python
@dataclass
class SparseVector:
    indices: list[int]      # Vi tri token trong khong gian hash
    values: list[float]     # Trong so tuong ung

    def as_object(self) -> dict:
        return {"indices": self.indices, "values": self.values}


@dataclass
class HybridEmbedding:
    dense: list[float]           # Vector dense (1024 dims cho BGE-M3)
    sparse: SparseVector         # Vector sparse
```

---

## 4. VietnameseLexicalSparseEncoder

Class nay tao sparse vectors bang phuong phap **feature hashing**
chuyen biet cho tieng Viet.

### 4.1 Khoi tao

```python
class VietnameseLexicalSparseEncoder:
    def __init__(self, hash_dim=2_000_003, use_bigrams=True):
        self.hash_dim = hash_dim       # Kich thuoc khong gian hash
        self.use_bigrams = use_bigrams # Co dung bigram khong
```

Cau hinh qua env vars:
- `SPARSE_HASH_DIM`: Kich thuoc hash (default 2000003 - so nguyen to)
- `SPARSE_USE_BIGRAMS`: True/False

### 4.2 Tokenize

```python
def tokenize(self, text: str) -> list[str]:
    # 1. Token hoa Unicode (giu dau tieng Viet)
    base_tokens = regex_findall(r"\w+", text.lower())

    # 2. Token hoa ASCII (bo dau)
    ascii_tokens = regex_findall(r"[a-z0-9]+", ascii_normalize(text))

    # 3. Merge ca 2 dang
    merged = base_tokens + ascii_tokens

    # 4. Loc: loai 1-char (tru so), loai stopwords
    filtered = [t for t in merged if len(t) > 1 and t not in VI_STOPWORDS]

    # 5. Them bigrams (neu bat)
    if use_bigrams and len(filtered) >= 2:
        filtered += [f"{a}_{b}" for a, b in zip(filtered, filtered[1:])]

    return filtered
```

**VI_STOPWORDS** - Cac tu dung tieng Viet bi loai:
```python
VI_STOPWORDS = {
    "va", "voi", "cua", "cho", "mot", "nhung", "cac",
    "la", "co", "mon", "thuc", "pham", "nhom", "nguon",
}
```

### 4.3 Hash Function

```python
def _hash_token(self, token: str) -> int:
    # Dung blake2b voi digest_size=8 bytes
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % self.hash_dim
```

**Tai sao blake2b?**
- Nhanh hon SHA-256
- Digest size nho (8 bytes) cho hash dim < 2^64
- Phan phoi deu, it collision

### 4.4 Embed

```python
def embed(self, text: str) -> SparseVector:
    tokens = self.tokenize(text)
    counts = Counter(tokens)

    weighted = {}
    for token, count in counts.items():
        index = self._hash_token(token)
        weight = 1.0 + math.log1p(count)  # Sublinear TF
        weighted[index] = weighted.get(index, 0.0) + weight

    indices = sorted(weighted.keys())
    values = [round(weighted[i], 6) for i in indices]
    return SparseVector(indices=indices, values=values)
```

**Weight formula**: `1.0 + log(1 + count)` = sublinear TF weighting.
Token xuat hien nhieu van co weight cao nhung tang cham lai.

### 4.5 Vi du

```
Input: "Uc ga luoc giau dam protein"

base_tokens:  ["uc", "ga", "luoc", "giau", "dam", "protein"]
ascii_tokens: ["uc", "ga", "luoc", "giau", "dam", "protein"]
merged:       ["uc", "ga", "luoc", "giau", "dam", "protein",
               "uc", "ga", "luoc", "giau", "dam", "protein"]
filtered:     ["uc", "ga", "luoc", "giau", "dam", "protein"] (dedup by stopwords)
bigrams:      ["uc_ga", "ga_luoc", "luoc_giau", "giau_dam", "dam_protein"]

-> SparseVector(
    indices=[12345, 23456, 34567, ...],  # hash cua tung token
    values=[1.693, 1.693, 1.693, ...]     # 1 + log(1+2) cho tokens xuat hien 2 lan
)
```

---

## 5. BGEEmbeddingService

### 5.1 Khoi tao

```python
class BGEEmbeddingService:
    def __init__(self):
        self.model_name = env("LOCAL_EMBEDDING_MODEL") or "BAAI/bge-m3"
        self.sparse_strategy = ...   # "bge_m3_native" hoac "vi_lexical"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Chi 1 trong 2 nhanh:
        if self.sparse_strategy == "bge_m3_native":
            self._native_bge_m3 = BGEM3FlagModel(model_name, use_fp16=...)
        else:
            self._dense_model = SentenceTransformer(model_name, device=...)
            self._lexical_sparse = VietnameseLexicalSparseEncoder(...)
```

### 5.2 encode_hybrid_batch(texts) -> list[HybridEmbedding]

**Native BGE-M3:**
```python
result = self._native_bge_m3.encode(
    texts,
    return_dense=True,
    return_sparse=True,
    return_colbert_vecs=False,
)
# Tra ve dense_vecs + lexical_weights tu cung 1 forward pass
```

**SentenceTransformer + Vi Lexical:**
```python
dense_embeddings = self._dense_model.encode(texts, normalize_embeddings=True)
sparse_vectors = [self._lexical_sparse.embed(text) for text in texts]
# Ket hop tu 2 model rieng biet
```

### 5.3 Convenience Methods

```python
encode_hybrid(text)     -> HybridEmbedding    # Single text
embed_dense(text)       -> list[float]         # Chi dense
embed_sparse(text)      -> SparseVector        # Chi sparse
embed_query(text)       -> list[float]         # Alias cho embed_dense
embed_document(text)    -> list[float]         # Alias cho embed_dense
```

---

## 6. Reranking

### 6.1 Tong quan

```
Candidates (tu Qdrant hybrid search)
         |
    +----+----+
    |         |
 Native    Fallback
 Rerank    Rerank
    |         |
    +----+----+
         |
  Reranked Scores
```

### 6.2 Native BGE-M3 Rerank

Dung khi: `enable_native_rerank=True` VA `_native_bge_m3` co san.

```python
def _native_rerank_documents(self, query, docs):
    # Chay trong ProcessPoolExecutor rieng biet (1 worker)
    sentence_pairs = [[query[:512], doc[:512]] for doc in docs]

    # Goi compute_score cua BGEM3FlagModel
    result = model.compute_score(
        sentence_pairs,
        max_passage_length=256,
        weights_for_different_modes=[0.4, 0.2, 0.4],
        # [colbert, sparse, dense] weights
    )
```

**Rerank tren subprocess** (ProcessPoolExecutor):
- Tranh block main thread
- Timeout: `RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS` (default 25s)
- Max docs: `RETRIEVAL_NATIVE_RERANK_MAX_DOCS` (default 6)
- Max chars/doc: `RETRIEVAL_NATIVE_RERANK_MAX_CHARS` (default 512)

**Blending khi docs > max_docs:**
```
native_head = native_rerank(docs[:6])
fallback_all = fallback_rerank(docs)

normalized_native = normalize(native_head)
normalized_fallback = normalize(fallback_all)

blended[0:6] = 0.80 * normalized_native + 0.20 * normalized_fallback
blended[6:]  = 0.92 * normalized_fallback[6:]
```

### 6.3 Fallback Rerank

Dung khi: native rerank khong kha dung (tat, loi, timeout).

```python
def _fallback_rerank_documents(self, query, docs):
    query_embedding = self.encode_hybrid(query)
    doc_embeddings = self.encode_hybrid_batch(docs)

    for doc, embedding in zip(docs, doc_embeddings):
        # Cosine similarity (da normalize)
        dense_score = dot_product(query_embedding.dense, embedding.dense)
        # Lexical overlap
        lexical_overlap = |query_tokens & doc_tokens| / |query_tokens|
        # Ket hop
        score = 0.75 * dense_score + 0.25 * lexical_overlap
```

### 6.4 Error Handling

Khi native rerank fail (timeout, crash, error):
1. Reset ProcessPoolExecutor
2. Log warning voi chi tiet
3. Fallback sang lexical+dense scoring
4. Khong crash, van tra ve ket qua

---

## 7. Cau hinh qua Environment Variables

| Env Var                                  | Default      | Mo ta                           |
|------------------------------------------|--------------|---------------------------------|
| `LOCAL_EMBEDDING_MODEL`                  | BAAI/bge-m3  | Ten model embedding             |
| `SPARSE_EMBEDDING_STRATEGY`              | auto         | auto/bge_m3_native/vi_lexical   |
| `SPARSE_HASH_DIM`                        | 2000003      | Kich thuoc hash space           |
| `SPARSE_USE_BIGRAMS`                     | true         | Su dung bigram                  |
| `RETRIEVAL_ENABLE_NATIVE_RERANK`         | false        | Bat native rerank               |
| `RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS`| 25           | Timeout cho native rerank       |
| `RETRIEVAL_NATIVE_RERANK_MAX_DOCS`       | 6            | So doc toi da cho native rerank |
| `RETRIEVAL_NATIVE_RERANK_MAX_CHARS`      | 512          | Max chars/doc cho rerank        |
| `RETRIEVAL_RERANK_MAX_PASSAGE_LENGTH`    | 256          | Max passage length cho rerank   |
| `RETRIEVAL_RERANK_WEIGHTS`               | 0.4,0.2,0.4  | [colbert, sparse, dense]       |

---

## 8. Factory Pattern (embedding_factory.py)

### 8.1 BaseEmbeddingService Interface

```python
class BaseEmbeddingService:
    def embed_text(self, text: str, is_query: bool = False) -> List[float]: ...
    def embed_batch(self, texts: List[str], is_query: bool = False) -> List[List[float]]: ...
```

### 8.2 Implementations

**GeminiEmbeddingService** (Cloud):
- Su dung Google Gemini API (`text-embedding-004`)
- Output: 768 dimensions
- Ho tro `task_type`: "retrieval_query" vs "retrieval_document"
- Fallback gracefully neu thieu API key

**LocalEmbeddingService** (Local):
- Su dung SentenceTransformer
- Ho tro E5 prefix ("query: " / "passage: ")
- Auto fp16 tren CUDA
- Batch size: 32

### 8.3 Factory Function

```python
def get_embedding_service() -> BaseEmbeddingService:
    if env("USE_LOCAL_EMBEDDING") == "true":
        model = env("LOCAL_EMBEDDING_MODEL") or "BAAI/bge-m3"
        return LocalEmbeddingService(model)
    else:
        api_key = env("GOOGLE_API_KEY")
        return GeminiEmbeddingService(api_key)
```

**Luu y:** Factory nay la phien ban cu (v1). He thong hien tai (v2)
su dung truc tiep `BGEEmbeddingService` qua `get_bge_service()`.

### 8.4 Singleton Pattern (BGEEmbeddingService)

```python
_service_instance = None

def get_bge_service():
    global _service_instance
    if _service_instance is None:
        _service_instance = BGEEmbeddingService()
    return _service_instance
```

Singleton dam bao model chi duoc load 1 lan trong toan bo vong doi app.

---

## 9. So sanh 2 chien luoc Sparse

| Tieu chi              | bge_m3_native                    | vi_lexical                        |
|-----------------------|----------------------------------|-----------------------------------|
| Model                 | FlagEmbedding BGEM3FlagModel     | VietnameseLexicalSparseEncoder    |
| Dense + Sparse        | Cung 1 forward pass              | 2 model rieng biet                |
| Chat luong sparse     | Hoc tu data (neural)             | Feature hashing (statistical)     |
| Toc do                | Cham hon (model lon)             | Nhanh hon (chi hash)              |
| Dependencies          | FlagEmbedding (co the loi)       | Chi can hashlib (built-in)        |
| Tieng Viet            | Tot (multilingual model)         | Tot (xoa dau + bigrams)           |
| RAM                   | Cao (load full model)            | Thap                              |

---

## 10. Lien ket tai lieu

- [CanonicalKnowledgeService](./canonical-knowledge.md) - Su dung embedding cho truy hoi
- [NutritionWorkflowService](./nutrition-workflow.md) - Bo dieu phoi chinh
- [NutritionService](./nutrition-optimizer.md) - Tinh TDEE va macro
- [NutritionIntentService](./intent-service.md) - Phan tich y dinh
