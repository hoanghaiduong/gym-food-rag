# import os
# from typing import List
# import torch
# from sentence_transformers import SentenceTransformer
# from dotenv import load_dotenv

# load_dotenv()

# class BGEEmbeddingService:
#     """
#     Service V2: Chuyên dụng cho model BAAI/bge-m3 (FlagEmbedding).
#     Output Dimension: 1024
#     """
#     def __init__(self):
#         # Hardcode model tốt nhất hoặc lấy từ ENV nhưng default là BGE-M3
#         self.model_name = os.getenv("V2_EMBEDDING_MODEL", "BAAI/bge-m3")
#         print(f"🚀 [API v2] Đang khởi tạo BGE-M3 Model: {self.model_name}...")
        
#         device = "cuda" if torch.cuda.is_available() else "cpu"
#         print(f"⚙️ [API v2] Running on device: {device.upper()}")
        
#         try:
#             self.model = SentenceTransformer(self.model_name, device=device)
#             # BGE-M3 hỗ trợ fp16 giúp giảm 50% RAM/VRAM mà không giảm chất lượng
#             if device == "cuda":
#                 self.model.half()
#             print("✅ [API v2] BGE-M3 Ready!")
#         except Exception as e:
#             print(f"❌ [API v2] Error loading model: {e}")
#             raise e

#     def embed_query(self, text: str) -> List[float]:
#         """
#         Dành cho câu hỏi của user.
#         BGE-M3 không bắt buộc prefix 'query:', nhưng thêm vào cũng tốt.
#         """
#         # BGE-M3 tự động xử lý rất tốt, ta dùng dense vector (output đầu tiên)
#         embeddings = self.model.encode(
#             [text], 
#             convert_to_numpy=True, 
#             normalize_embeddings=True
#         )
#         return embeddings[0].tolist()

#     def embed_document(self, text: str) -> List[float]:
#         """Dành cho việc nạp dữ liệu vào DB"""
#         embeddings = self.model.encode(
#             [text], 
#             convert_to_numpy=True, 
#             normalize_embeddings=True
#         )
#         return embeddings[0].tolist()

# # Singleton instance
# # Chỉ khởi tạo khi được gọi import để tiết kiệm tài nguyên nếu chưa dùng tới
# _service_instance = None

# def get_bge_service():
#     global _service_instance
#     if _service_instance is None:
#         _service_instance = BGEEmbeddingService()
#     return _service_instance


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