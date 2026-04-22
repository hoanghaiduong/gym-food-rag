"""Knowledge retrieval package."""

from .local_index import (
    FOODS_JSONL_PATH,
    MASTER_JSONL_PATH,
    QDRANT_READY_JSONL_PATH,
    default_runtime_jsonl_path,
)
from .normalize import (
    ascii_normalize,
    format_metric,
    normalize_unicode_text,
    normalized_tokens,
    raw_normalize,
    raw_tokens,
    safe_float,
    sanitize_json_payload,
)
from .payloads import (
    build_canonical_content,
    build_dense_text,
    build_hybrid_text,
    build_sparse_text,
    build_vector_payload,
    is_qdrant_ready_record,
    payload_to_food,
)
from .service import CanonicalKnowledgeService, canonical_knowledge_service
from .tags import derive_allergen_tags, derive_diet_tags

__all__ = [
    "FOODS_JSONL_PATH",
    "MASTER_JSONL_PATH",
    "QDRANT_READY_JSONL_PATH",
    "CanonicalKnowledgeService",
    "ascii_normalize",
    "build_canonical_content",
    "build_dense_text",
    "build_hybrid_text",
    "build_sparse_text",
    "build_vector_payload",
    "canonical_knowledge_service",
    "default_runtime_jsonl_path",
    "derive_allergen_tags",
    "derive_diet_tags",
    "format_metric",
    "is_qdrant_ready_record",
    "normalize_unicode_text",
    "normalized_tokens",
    "payload_to_food",
    "raw_normalize",
    "raw_tokens",
    "safe_float",
    "sanitize_json_payload",
]
