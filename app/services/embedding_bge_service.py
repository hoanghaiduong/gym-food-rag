import hashlib
import math
import multiprocessing as mp
import os
import re
import unicodedata
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from typing import Iterable, List

import torch

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional for lightweight CLI environments
    def load_dotenv(*args, **kwargs):
        return False

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:  # pragma: no cover - optional at import time
    SentenceTransformer = None


load_dotenv()

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
VI_STOPWORDS = {
    "va",
    "voi",
    "cua",
    "cho",
    "mot",
    "nhung",
    "cac",
    "la",
    "co",
    "mon",
    "thuc",
    "pham",
    "nhom",
    "nguon",
}

_FLAG_EMBEDDING_MODEL = None
_FLAG_EMBEDDING_IMPORT_ATTEMPTED = False
_FLAG_EMBEDDING_IMPORT_ERROR = None
_NATIVE_RERANK_EXECUTOR = None
_NATIVE_RERANK_WORKER_MODEL = None


def ascii_normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().split())


def _native_rerank_worker_init(model_name: str, use_fp16: bool) -> None:
    global _NATIVE_RERANK_WORKER_MODEL
    if _NATIVE_RERANK_WORKER_MODEL is not None:
        return
    from FlagEmbedding import BGEM3FlagModel

    _NATIVE_RERANK_WORKER_MODEL = BGEM3FlagModel(
        model_name,
        use_fp16=use_fp16,
    )


def _native_rerank_worker_score(
    sentence_pairs: list[list[str]],
    max_passage_length: int,
    rerank_weights: list[float],
) -> list[float]:
    global _NATIVE_RERANK_WORKER_MODEL
    if _NATIVE_RERANK_WORKER_MODEL is None:
        raise RuntimeError("Native rerank worker model is not initialized.")

    result = _NATIVE_RERANK_WORKER_MODEL.compute_score(
        sentence_pairs,
        max_passage_length=max_passage_length,
        weights_for_different_modes=rerank_weights,
    )
    for key in [
        "colbert+sparse+dense",
        "sparse+dense",
        "dense",
        "sparse",
        "colbert",
    ]:
        if key in result:
            return [float(score) for score in result[key]]
    raise RuntimeError("Native rerank worker did not return a supported score key.")


@dataclass
class SparseVector:
    indices: list[int]
    values: list[float]

    def as_object(self) -> dict[str, list[int] | list[float]]:
        return {
            "indices": self.indices,
            "values": self.values,
        }


@dataclass
class HybridEmbedding:
    dense: list[float]
    sparse: SparseVector


class VietnameseLexicalSparseEncoder:
    def __init__(self, *, hash_dim: int = 2_000_003, use_bigrams: bool = True):
        self.hash_dim = hash_dim
        self.use_bigrams = use_bigrams

    def tokenize(self, text: str) -> list[str]:
        base_tokens = [token.lower() for token in TOKEN_PATTERN.findall(text or "")]
        ascii_tokens = [token for token in TOKEN_PATTERN.findall(ascii_normalize(text or "")) if token]
        merged = base_tokens + ascii_tokens
        filtered = [
            token
            for token in merged
            if token
            and (len(token) > 1 or token.isdigit())
            and token not in VI_STOPWORDS
        ]
        if self.use_bigrams and len(filtered) >= 2:
            filtered.extend(f"{left}_{right}" for left, right in zip(filtered, filtered[1:]))
        return filtered

    def _hash_token(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.hash_dim

    def embed(self, text: str) -> SparseVector:
        tokens = self.tokenize(text)
        if not tokens:
            return SparseVector(indices=[], values=[])

        counts = Counter(tokens)
        weighted: dict[int, float] = {}
        for token, count in counts.items():
            index = self._hash_token(token)
            weight = 1.0 + math.log1p(count)
            weighted[index] = weighted.get(index, 0.0) + weight

        indices = sorted(weighted.keys())
        values = [round(weighted[index], 6) for index in indices]
        return SparseVector(indices=indices, values=values)


class BGEEmbeddingService:
    def __init__(self):
        self.model_name = (
            os.getenv("LOCAL_EMBEDDING_MODEL")
            or os.getenv("V2_EMBEDDING_MODEL")
            or "BAAI/bge-m3"
        )
        requested_strategy = os.getenv("SPARSE_EMBEDDING_STRATEGY", "auto").strip().lower()
        self.sparse_hash_dim = int(os.getenv("SPARSE_HASH_DIM", "2000003"))
        self.sparse_use_bigrams = os.getenv("SPARSE_USE_BIGRAMS", "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        self.enable_native_rerank = os.getenv("RETRIEVAL_ENABLE_NATIVE_RERANK", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        self.native_rerank_timeout_seconds = int(os.getenv("RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS", "25"))
        self.native_rerank_max_docs = int(os.getenv("RETRIEVAL_NATIVE_RERANK_MAX_DOCS", "6"))
        self.native_rerank_max_chars = int(os.getenv("RETRIEVAL_NATIVE_RERANK_MAX_CHARS", "512"))
        self.rerank_max_passage_length = int(os.getenv("RETRIEVAL_RERANK_MAX_PASSAGE_LENGTH", "256"))
        self.rerank_weights = self._parse_rerank_weights(
            os.getenv("RETRIEVAL_RERANK_WEIGHTS", "0.4,0.2,0.4")
        )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self._native_bge_m3 = None
        self._dense_model = None
        self._lexical_sparse = None

        if requested_strategy == "auto":
            if self.model_name == "BAAI/bge-m3" and self._can_use_native_bge_m3():
                self.sparse_strategy = "bge_m3_native"
            else:
                self.sparse_strategy = "vi_lexical"
        else:
            self.sparse_strategy = requested_strategy

        if self.sparse_strategy == "bge_m3_native":
            if self.model_name != "BAAI/bge-m3":
                raise ValueError("bge_m3_native sparse strategy requires LOCAL_EMBEDDING_MODEL=BAAI/bge-m3")
            native_model_cls = self._require_native_bge_m3()
            print(f"[Embedding] Loading native BGE-M3 dense+sparse: {self.model_name}")
            self._native_bge_m3 = native_model_cls(
                self.model_name,
                use_fp16=self.device == "cuda",
            )
        else:
            if SentenceTransformer is None:
                raise ModuleNotFoundError(
                    "sentence-transformers is required for dense embedding fallback. "
                    "Install dependencies from requirements.txt."
                )
            print(f"[Dense] Loading multilingual embedding model: {self.model_name}")
            self._dense_model = SentenceTransformer(self.model_name, device=self.device)
            if self.device == "cuda":
                self._dense_model.half()
            print(
                f"[Sparse] Using Vietnamese lexical sparse encoder "
                f"(strategy={self.sparse_strategy}, hash_dim={self.sparse_hash_dim}, "
                f"bigrams={self.sparse_use_bigrams})"
            )
            self._lexical_sparse = VietnameseLexicalSparseEncoder(
                hash_dim=self.sparse_hash_dim,
                use_bigrams=self.sparse_use_bigrams,
            )

    def _can_use_native_bge_m3(self) -> bool:
        model_cls, _ = self._load_native_bge_m3_class()
        return model_cls is not None

    def _require_native_bge_m3(self):
        model_cls, exc = self._load_native_bge_m3_class()
        if model_cls is None:
            detail = f"{type(exc).__name__}: {exc}" if exc is not None else "unknown import error"
            raise RuntimeError(
                "Native BGE-M3 sparse mode requires a working FlagEmbedding installation, "
                f"but importing it failed: {detail}. "
                "Keep SPARSE_EMBEDDING_STRATEGY=auto to fall back safely, or align "
                "FlagEmbedding and transformers versions if you want native sparse."
            ) from exc
        return model_cls

    def _load_native_bge_m3_class(self):
        global _FLAG_EMBEDDING_MODEL
        global _FLAG_EMBEDDING_IMPORT_ATTEMPTED
        global _FLAG_EMBEDDING_IMPORT_ERROR

        if not _FLAG_EMBEDDING_IMPORT_ATTEMPTED:
            _FLAG_EMBEDDING_IMPORT_ATTEMPTED = True
            try:
                from FlagEmbedding import BGEM3FlagModel as native_model_cls
            except Exception as exc:  # pragma: no cover - environment compatibility guard
                _FLAG_EMBEDDING_MODEL = None
                _FLAG_EMBEDDING_IMPORT_ERROR = exc
                print(
                    "[Embedding] Native BGE-M3 unavailable; falling back to Vietnamese lexical sparse. "
                    f"Reason: {type(exc).__name__}: {exc}"
                )
            else:
                _FLAG_EMBEDDING_MODEL = native_model_cls
                _FLAG_EMBEDDING_IMPORT_ERROR = None

        return _FLAG_EMBEDDING_MODEL, _FLAG_EMBEDDING_IMPORT_ERROR

    def _parse_rerank_weights(self, raw_value: str) -> list[float]:
        try:
            weights = [float(item.strip()) for item in raw_value.split(",") if item.strip()]
        except ValueError:
            weights = [0.4, 0.2, 0.4]
        if len(weights) != 3:
            return [0.4, 0.2, 0.4]
        return weights

    def _get_native_rerank_executor(self) -> ProcessPoolExecutor:
        global _NATIVE_RERANK_EXECUTOR
        if _NATIVE_RERANK_EXECUTOR is None:
            _NATIVE_RERANK_EXECUTOR = ProcessPoolExecutor(
                max_workers=1,
                mp_context=mp.get_context("spawn"),
                initializer=_native_rerank_worker_init,
                initargs=(self.model_name, self.device == "cuda"),
            )
        return _NATIVE_RERANK_EXECUTOR

    def _reset_native_rerank_executor(self) -> None:
        global _NATIVE_RERANK_EXECUTOR
        if _NATIVE_RERANK_EXECUTOR is not None:
            _NATIVE_RERANK_EXECUTOR.shutdown(wait=False, cancel_futures=True)
            _NATIVE_RERANK_EXECUTOR = None

    def _native_rerank_documents(self, query: str, docs: list[str]) -> list[float]:
        if not self.enable_native_rerank or self._native_bge_m3 is None:
            raise RuntimeError("Native rerank is disabled or unavailable.")

        sentence_pairs = [
            [
                query[: self.native_rerank_max_chars],
                doc[: self.native_rerank_max_chars],
            ]
            for doc in docs
        ]
        executor = self._get_native_rerank_executor()
        future = executor.submit(
            _native_rerank_worker_score,
            sentence_pairs,
            self.rerank_max_passage_length,
            self.rerank_weights,
        )
        return future.result(timeout=self.native_rerank_timeout_seconds)

    def _normalize_score_list(self, values: list[float]) -> list[float]:
        if not values:
            return []
        low = min(values)
        high = max(values)
        if math.isclose(low, high):
            return [1.0 for _ in values]
        return [(value - low) / (high - low) for value in values]

    def _fallback_rerank_documents(
        self,
        query: str,
        docs: list[str],
    ) -> list[float]:
        query_embedding = self.encode_hybrid(query)
        doc_embeddings = self.encode_hybrid_batch(docs)
        lexical_encoder = self._lexical_sparse or VietnameseLexicalSparseEncoder(
            hash_dim=self.sparse_hash_dim,
            use_bigrams=self.sparse_use_bigrams,
        )
        query_tokens = set(lexical_encoder.tokenize(query))
        scores: list[float] = []
        for doc, embedding in zip(docs, doc_embeddings):
            dense_score = sum(left * right for left, right in zip(query_embedding.dense, embedding.dense))
            doc_tokens = set(lexical_encoder.tokenize(doc))
            lexical_overlap = len(query_tokens & doc_tokens) / max(len(query_tokens), 1)
            scores.append(0.75 * dense_score + 0.25 * lexical_overlap)
        return scores

    def _sparse_from_lexical_weights(self, lexical_weights: dict) -> SparseVector:
        pairs = sorted(
            (int(index), float(value))
            for index, value in (lexical_weights or {}).items()
            if value is not None
        )
        return SparseVector(
            indices=[index for index, _ in pairs],
            values=[value for _, value in pairs],
        )

    def encode_hybrid(self, text: str) -> HybridEmbedding:
        return self.encode_hybrid_batch([text])[0]

    def encode_hybrid_batch(self, texts: list[str]) -> list[HybridEmbedding]:
        if not texts:
            return []

        if self._native_bge_m3 is not None:
            result = self._native_bge_m3.encode(
                texts,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            embeddings: list[HybridEmbedding] = []
            for dense_vec, lexical_weights in zip(
                result["dense_vecs"],
                result["lexical_weights"],
            ):
                dense = dense_vec.tolist() if hasattr(dense_vec, "tolist") else list(dense_vec)
                sparse = self._sparse_from_lexical_weights(lexical_weights)
                embeddings.append(HybridEmbedding(dense=dense, sparse=sparse))
            return embeddings

        dense_embeddings = self._dense_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return [
            HybridEmbedding(
                dense=dense_embeddings[index].tolist(),
                sparse=self._lexical_sparse.embed(text),
            )
            for index, text in enumerate(texts)
        ]

    def embed_dense(self, text: str) -> List[float]:
        return self.encode_hybrid(text).dense

    def embed_sparse(self, text: str) -> SparseVector:
        return self.encode_hybrid(text).sparse

    def rerank_documents(self, query: str, documents: Iterable[str]) -> list[float]:
        docs = list(documents)
        if not docs:
            return []

        if self._native_bge_m3 is not None and self.enable_native_rerank:
            native_head_size = min(len(docs), self.native_rerank_max_docs)
            try:
                native_scores = self._native_rerank_documents(query, docs[:native_head_size])
                if native_head_size == len(docs):
                    return native_scores

                fallback_scores = self._fallback_rerank_documents(query, docs)
                normalized_native = self._normalize_score_list(native_scores)
                normalized_fallback = self._normalize_score_list(fallback_scores)
                blended_scores = list(normalized_fallback)
                for index in range(native_head_size):
                    blended_scores[index] = (
                        0.80 * normalized_native[index]
                        + 0.20 * normalized_fallback[index]
                    )
                for index in range(native_head_size, len(blended_scores)):
                    blended_scores[index] = 0.92 * blended_scores[index]
                return blended_scores
            except (FuturesTimeoutError, BrokenProcessPool, RuntimeError, Exception) as exc:
                self._reset_native_rerank_executor()
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "Native BGEM3 rerank timeout/failed",
                    extra={
                        "error_type": type(exc).__name__,
                        "timeout_seconds": self.native_rerank_timeout_seconds,
                        "docs_count": len(docs),
                        "query_length": len(query),
                        "recommendation": "Increase RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS or reduce max_docs"
                    }
                )
                print(
                    "[Rerank] Native BGEM3 rerank unavailable for this request; "
                    f"falling back to lexical+dense scoring. Reason: {type(exc).__name__}: {exc}"
                )

        return self._fallback_rerank_documents(query, docs)

    def embed_query(self, text: str) -> List[float]:
        return self.embed_dense(text)

    def embed_document(self, text: str) -> List[float]:
        return self.embed_dense(text)


_service_instance = None


def get_bge_service():
    global _service_instance
    if _service_instance is None:
        _service_instance = BGEEmbeddingService()
    return _service_instance
