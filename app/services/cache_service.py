import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models
from datetime import datetime

class SemanticCacheService:
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", 6333))
        # Kết nối client
        self.client = QdrantClient(host=self.host, port=self.port)
        
        self.collection_name = "gym_chat_cache"
        self.threshold = 0.95 
        
        # Biến cờ để đánh dấu trạng thái khởi tạo
        self._is_initialized = False

    def _ensure_collection(self):
        """
        Cơ chế Lazy Loading: Chỉ tạo collection khi thực sự cần dùng.
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
            
            self._is_initialized = True
            
        except Exception as e:
            print(f"⚠️ [Cache Init Warning] Không thể kết nối Qdrant: {e}")

    def check_cache(self, vector_query: list):
        """
        Tìm kiếm câu trả lời đã có trong quá khứ.
        """
        self._ensure_collection()
        
        if not self._is_initialized:
            return None

        try:
            # [CHUẨN MỚI] Sử dụng query_points với tham số 'query'
            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=vector_query, # Sửa từ query_vector -> query
                limit=1,
                score_threshold=self.threshold 
            )
            
            # Kiểm tra kết quả trong danh sách points
            if search_result.points:
                hit = search_result.points[0]
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
        self._ensure_collection()

        if not self._is_initialized:
            return

        # --- [AN TOÀN] CHỐNG LƯU LỖI VÀO CACHE ---
        # Nếu câu trả lời chứa các từ khóa lỗi, tuyệt đối không lưu
        error_keywords = ["Lỗi kết nối", "Error:", "Exception:", "tôi chưa tìm thấy thông tin"]
        if any(kw in answer for kw in error_keywords) or len(answer) < 10:
            print(f"🛑 [CACHE SKIP] Phát hiện nội dung lỗi hoặc quá ngắn, không lưu cache.")
            return
        # -------------------------------------------

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