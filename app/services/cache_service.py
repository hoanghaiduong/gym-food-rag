import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from datetime import datetime

class SemanticCacheService:
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", 6333))
        # Kết nối client nhưng chưa gọi API ngay
        self.client = QdrantClient(host=self.host, port=self.port)
        
        self.collection_name = "gym_chat_cache"
        self.threshold = 0.95 
        
        # [FIX]: Dùng biến cờ để đánh dấu trạng thái khởi tạo
        self._is_initialized = False

    def _ensure_collection(self):
        """
        Cơ chế Lazy Loading: Chỉ tạo collection khi thực sự cần dùng.
        Nếu lần đầu thất bại (do Qdrant chưa up), lần sau gọi lại sẽ thử tạo lại.
        """
        if self._is_initialized:
            return

        try:
            # Kiểm tra collection
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                print(f"📦 [Cache] Đang tạo bộ nhớ đệm mới: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=1024,  # Đảm bảo khớp với model embedding (BGE-M3 = 1024)
                        distance=models.Distance.COSINE
                    )
                )
                print(f"✅ [Cache] Đã tạo collection '{self.collection_name}' thành công.")
            
            # Đánh dấu đã khởi tạo thành công để không check lại nhiều lần
            self._is_initialized = True
            
        except Exception as e:
            # Log lỗi nhưng không crash, để lần sau thử lại
            print(f"⚠️ [Cache Init Warning] Không thể kết nối Qdrant: {e}")

    def check_cache(self, vector_query: list):
        """
        Tìm kiếm câu trả lời đã có trong quá khứ.
        """
        # [FIX]: Luôn đảm bảo collection tồn tại trước khi search
        self._ensure_collection()
        
        # Nếu vẫn chưa init được (do Qdrant chết), trả về None luôn để tránh lỗi crash
        if not self._is_initialized:
            return None

        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector_query,
                limit=1,
                score_threshold=self.threshold 
            )
            
            if search_result:
                hit = search_result[0]
                print(f"🔥 [CACHE HIT] Tìm thấy câu trả lời cũ (Score: {hit.score:.4f})")
                return hit.payload['answer']
            
            print("❄️ [CACHE MISS] Không tìm thấy trong cache.")
            return None
        except Exception as e:
            print(f"⚠️ [Cache Read Error] {e}")
            return None

    def save_to_cache(self, vector_query: list, question: str, answer: str):
        """
        Lưu câu hỏi và câu trả lời mới vào Cache.
        """
        # [FIX]: Đảm bảo collection tồn tại trước khi lưu
        self._ensure_collection()

        if not self._is_initialized:
            return

        try:
            point_id = str(uuid.uuid4())
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector_query,
                        payload={
                            "question": question,
                            "answer": answer,
                            "created_at": datetime.now().isoformat()
                        }
                    )
                ]
            )
            print(f"💾 [CACHE SAVED] Đã lưu cache: '{question}'")
        except Exception as e:
            print(f"⚠️ [Cache Write Error] {e}")

# Singleton Instance
cache_service = SemanticCacheService()