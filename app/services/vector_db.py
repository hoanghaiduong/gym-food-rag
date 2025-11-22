from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import settings
from typing import List, Dict, Any

class QdrantService:
    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.collection_name = settings.COLLECTION_NAME

    def create_collection_if_not_exists(self, vector_size: int = 768):
        """Tạo collection nếu chưa có"""
        collections = self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
            )
            print(f"Đã tạo collection: {self.collection_name}")

    def upload_documents(self, documents: List[Dict[str, Any]], vectors: List[List[float]]):
        """Nạp dữ liệu vào Qdrant"""
        points = [
            models.PointStruct(
                id=idx,
                vector=vector,
                payload=doc
            )
            for idx, (doc, vector) in enumerate(zip(documents, vectors))
        ]
        
        # Upload theo batch để tối ưu
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def search_similar(self, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Tìm kiếm vector tương đồng"""
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit
        )
        
        # Trích xuất payload (dữ liệu gốc)
        return [hit.payload for hit in search_result]

vector_db = QdrantService()