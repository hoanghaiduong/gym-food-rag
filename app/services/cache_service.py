import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from datetime import datetime

class SemanticCacheService:
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", 6333))
        self.client = QdrantClient(host=self.host, port=self.port)
        
        # Tên collection dùng để lưu Cache
        self.collection_name = "gym_chat_cache"
        # Ngưỡng tương đồng (0.0 -> 1.0). 
        # Đặt 0.95 để đảm bảo chỉ câu hỏi RẤT GIỐNG nhau mới dùng lại câu trả lời.
        self.threshold = 0.95 
        
        # Tự động tạo collection cache nếu chưa có
        self._init_collection()

    def _init_collection(self):
        """
        Khởi tạo Collection Cache an toàn.
        Kiểm tra xem collection đã tồn tại chưa trước khi tạo.
        """
        try:
            # Lấy danh sách các collection hiện có
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                print(f"📦 [Cache] Đang tạo bộ nhớ đệm mới: {self.collection_name}")
                # Lưu ý: Vector size phải khớp với model embedding (BGE-M3 = 1024)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=1024, 
                        distance=models.Distance.COSINE
                    )
                )
            else:
                print(f"✅ [Cache] Collection '{self.collection_name}' đã sẵn sàng.")
                
        except Exception as e:
            # Log lỗi nhưng không crash app (có thể do lỗi mạng tạm thời)
            print(f"⚠️ [Cache Warning] Không thể kiểm tra/tạo collection: {e}")

    def check_cache(self, vector_query: list):
        """
        Tìm kiếm câu trả lời đã có trong quá khứ.
        """
        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector_query,
                limit=1,
                score_threshold=self.threshold # Chỉ lấy nếu độ giống > 95%
            )
            
            if search_result:
                hit = search_result[0]
                print(f"🔥 [CACHE HIT] Tìm thấy câu trả lời cũ (Score: {hit.score:.4f})")
                return hit.payload['answer']
            
            print("❄️ [CACHE MISS] Không tìm thấy trong cache, phải hỏi AI.")
            return None
        except Exception as e:
            print(f"⚠️ [Cache Warning] Lỗi khi đọc cache: {e}")
            return None

    def save_to_cache(self, vector_query: list, question: str, answer: str):
        """
        Lưu câu hỏi và câu trả lời mới vào Cache.
        """
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
            print(f"💾 [CACHE SAVED] Đã lưu câu trả lời cho: '{question}'")
        except Exception as e:
            print(f"⚠️ [Cache Warning] Lỗi khi lưu cache: {e}")

# Singleton
cache_service = SemanticCacheService()