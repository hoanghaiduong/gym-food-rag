import os
from typing import List
import torch
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
# Thêm import này
from fastembed import SparseTextEmbedding

load_dotenv()

class BGEEmbeddingService:
    def __init__(self):
        # 1. Load Model Dense (Như cũ)
        self.model_name = os.getenv("V2_EMBEDDING_MODEL", "BAAI/bge-m3")
        print(f"🚀 [Dense] Loading BGE-M3: {self.model_name}...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(self.model_name, device=device)
        if device == "cuda": self.model.half()
        
        # 2. Load Model Sparse (MỚI) - Dùng SPLADE rất nhẹ
        print(f"🚀 [Sparse] Loading SPLADE for Keywords...")
        self.sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
        print("✅ [Embedding] Hybrid Models Ready!")

    def embed_dense(self, text: str) -> List[float]:
        """Tạo Dense Vector (Ngữ nghĩa)"""
        embeddings = self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return embeddings[0].tolist()

    def embed_sparse(self, text: str):
        """Tạo Sparse Vector (Từ khóa) - MỚI"""
        # fastembed trả về generator, ta lấy phần tử đầu tiên
        return list(self.sparse_model.embed([text]))[0]

    # Giữ lại hàm cũ để tránh lỗi code cũ, trỏ về embed_dense
    def embed_query(self, text: str) -> List[float]:
        return self.embed_dense(text)

    def embed_document(self, text: str) -> List[float]:
        return self.embed_dense(text)

# Singleton
_service_instance = None
def get_bge_service():
    global _service_instance
    if _service_instance is None:
        _service_instance = BGEEmbeddingService()
    return _service_instance
    pass