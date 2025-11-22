import google.generativeai as genai
from app.core.config import settings

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash') #gemini-2.5-flash
        self.embedding_model = 'models/text-embedding-004'#text-embedding-004

    def get_embedding(self, text: str) -> list:
        """Chuyển đổi văn bản thành vector"""
        # Làm sạch văn bản cơ bản
        clean_text = text.replace("\n", " ")
        result = genai.embed_content(
            model=self.embedding_model,
            content=clean_text,
            task_type="retrieval_document"
        )
        return result['embedding']

    def generate_response(self, system_prompt: str, user_question: str, context: str) -> str:
        """Sinh câu trả lời dựa trên Context"""
        full_prompt = f"""
        {system_prompt}
        
        CONTEXT INFORMATION:
        {context}
        
        USER QUESTION:
        {user_question}
        """
        response = self.model.generate_content(full_prompt)
        return response.text

llm_service = GeminiService()