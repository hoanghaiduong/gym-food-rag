import os
import sys
from typing import List
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import torch

load_dotenv()

class BaseEmbeddingService:
    """Interface chuẩn cho mọi Embedding Service"""
    def embed_text(self, text: str, is_query: bool = False) -> List[float]:
        raise NotImplementedError
    
    def embed_batch(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        raise NotImplementedError

class GeminiEmbeddingService(BaseEmbeddingService):
    """Service xử lý Google Gemini API"""
    def __init__(self, api_key):
        if not api_key:
            # Fallback nếu chưa cấu hình, tránh crash app ngay lập tức
            print("⚠️ [Warning] Thiếu GOOGLE_API_KEY. Gemini Service sẽ không hoạt động.")
            return
        try:
            genai.configure(api_key=api_key)
            print("☁️ [System] Đã kích hoạt Gemini Embedding API (Cloud).")
        except Exception as e:
            print(f"❌ [Gemini Error] Lỗi cấu hình: {e}")

    def embed_batch(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        if not texts: return []
        try:
            # Gemini embedding-004 output 768 chiều
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=texts,
                task_type="retrieval_query" if is_query else "retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"❌ [Gemini Error] {e}")
            return []
    
    def embed_text(self, text: str, is_query: bool = False) -> List[float]:
        res = self.embed_batch([text], is_query)
        return res[0] if res else []
    
    @property
    def model_name(self):
        return "gemini-cloud-embedding"

class LocalEmbeddingService(BaseEmbeddingService):
    """Service xử lý các model Local (E5, MPNet, BGE-M3)"""
    def __init__(self, model_name):
        print(f"🚀 [System] Đang tải Local Model: {model_name}...")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"⚙️ [Info] Running on device: {device.upper()}")
        
        try:
            self.model = SentenceTransformer(model_name, device=device)
            self.model_name_str = model_name
            
            if device == "cuda":
                self.model.half()
                
            print(f"✅ [System] Model {model_name} đã sẵn sàng!")
        except Exception as e:
            print(f"❌ [Error] Không thể tải model: {e}")
            sys.exit(1)

    def _get_prefix(self, is_query: bool) -> str:
        name = self.model_name_str.lower()
        if "e5" in name:
            return "query: " if is_query else "passage: "
        return ""

    def embed_batch(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        if not texts: return []
        
        prefix = self._get_prefix(is_query)
        processed_texts = [f"{prefix}{t}" for t in texts] if prefix else texts
        
        embeddings = self.model.encode(
            processed_texts, 
            batch_size=32, 
            convert_to_numpy=True, 
            normalize_embeddings=True
        )
        return embeddings.tolist()

    def embed_text(self, text: str, is_query: bool = False) -> List[float]:
        return self.embed_batch([text], is_query)[0]
    
    @property
    def model_name(self):
        return self.model_name_str

# --- FACTORY FUNCTION ---
def get_embedding_service() -> BaseEmbeddingService:
    """
    Hàm Factory: Đọc .env và trả về Service class phù hợp.
    """
    use_local = os.getenv("USE_LOCAL_EMBEDDING", "False").lower() == "true"
    
    if use_local:
        model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-m3")
        return LocalEmbeddingService(model_name)
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        return GeminiEmbeddingService(api_key)