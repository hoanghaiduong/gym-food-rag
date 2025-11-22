import os
import requests
import google.generativeai as genai
from app.core.config import settings
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    """
    Unified Service: Hỗ trợ cả code cũ (V1) và khả năng mở rộng sang Ollama (V2).
    Tự động chuyển đổi Backend dựa trên file .env
    """
    def __init__(self):
        # 1. Load cấu hình Backend
        self.backend = os.getenv("LLM_BACKEND", "gemini").lower()
        
        # 2. Cấu hình Gemini (Luôn load để dùng cho Embedding cũ hoặc backup)
        try:
            # Dùng settings hoặc os.getenv đều được, ưu tiên os.getenv cho linh hoạt Docker
            api_key = os.getenv("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
                self.embedding_model = 'models/text-embedding-004'
        except Exception as e:
            print(f"⚠️ [LLM Service] Cảnh báo cấu hình Gemini: {e}")

        # 3. Cấu hình Ollama (Quan trọng cho Docker)
        # Lưu ý: Trong Docker, URL này thường là http://ollama:11434
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")

        print(f"⚙️ [LLM Service] Backend đang chạy: {self.backend.upper()}")
        if self.backend == "ollama":
            print(f"   ╰─ Model: {self.ollama_model} @ {self.ollama_url}")

    # --- METHOD 1: DÀNH CHO API V2 (FIX LỖI CỦA BẠN) ---
    def generate_answer(self, prompt: str) -> str:
        """
        Hàm đơn giản nhận vào 1 prompt lớn (đã bao gồm context) và trả về text.
        Dùng cho API V2.
        """
        if self.backend == "ollama":
            return self._call_ollama(prompt)
        else:
            return self._call_gemini(prompt)

    # --- METHOD 2: DÀNH CHO API V1 (LEGACY) ---
    def generate_response(self, system_prompt: str, user_question: str, context: str) -> str:
        """
        Hàm cũ nhận 3 tham số rời rạc. 
        Giữ lại để không làm hỏng code cũ.
        """
        full_prompt = f"""
        {system_prompt}
        
        CONTEXT INFORMATION:
        {context}
        
        USER QUESTION:
        {user_question}
        """
        # Tái sử dụng hàm generate_answer ở trên
        return self.generate_answer(full_prompt)

    # --- METHOD 3: EMBEDDING CŨ (LEGACY) ---
    def get_embedding(self, text: str) -> list:
        try:
            clean_text = text.replace("\n", " ")
            result = genai.embed_content(
                model=self.embedding_model,
                content=clean_text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"❌ Lỗi Embedding (Gemini Legacy): {e}")
            return []

    # --- INTERNAL WORKERS ---
    def _call_gemini(self, prompt: str) -> str:
        try:
            if not hasattr(self, 'gemini_model'):
                return "Lỗi: Chưa cấu hình API Key cho Gemini."
            response = self.gemini_model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Lỗi Gemini API: {str(e)}"

    def _call_ollama(self, prompt: str) -> str:
        try:
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 4096 
                }
            }
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=60)
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                return f"Lỗi Ollama ({response.status_code}): {response.text}"
        except Exception as e:
            return f"Không kết nối được Ollama tại {self.ollama_url}: {str(e)}"

# --- SINGLETON ACCESSOR ---
_llm_instance = None

def get_llm_service():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance

# Legacy instance export
llm_service = get_llm_service()