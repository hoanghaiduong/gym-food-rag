from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
except ModuleNotFoundError:  # pragma: no cover - allows tooling without qdrant client installed
    QdrantClient = None
    models = None

from app.core.config import settings
from app.services.embedding_bge_service import get_bge_service

from .local_index import LocalIndexMixin, default_runtime_jsonl_path
from .qdrant_filters import QdrantFilterMixin
from .repository import RepositoryMixin
from .rerank import RerankMixin


class CanonicalKnowledgeService(LocalIndexMixin, QdrantFilterMixin, RerankMixin, RepositoryMixin):
    def __init__(self, jsonl_path: Optional[Path] = None):
        if QdrantClient is None or models is None:
            raise ModuleNotFoundError(
                "qdrant_client is required to use CanonicalKnowledgeService. "
                "Install backend dependencies before starting the retrieval service."
            )
        self.collection_name = settings.serving_collection_name
        self.jsonl_path = jsonl_path or default_runtime_jsonl_path()
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=20)
        self.models = models
        self._embedder = None
        self._records_by_entity_id: Optional[dict[str, dict[str, Any]]] = None
        self._records_by_name: Optional[dict[str, dict[str, Any]]] = None
        self._records_by_family_key: Optional[dict[str, list[dict[str, Any]]]] = None
        self._all_records_by_entity_id: Optional[dict[str, dict[str, Any]]] = None
        self._all_records_by_name: Optional[dict[str, dict[str, Any]]] = None
        self._all_records_by_family_key: Optional[dict[str, list[dict[str, Any]]]] = None

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = get_bge_service()
        return self._embedder


canonical_knowledge_service = CanonicalKnowledgeService()
