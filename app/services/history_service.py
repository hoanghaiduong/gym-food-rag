import json
from sqlalchemy.orm import Session  # Import thêm Session để type hint
from sqlalchemy import insert, select, desc, delete
from app.db.schemas import chat_history

class HistoryService:
    def __init__(self, db_session: Session): 
        self.db_session = db_session  # Lưu vào biến self.db_session

    async def save_interaction(self, user_id: int, question: str, answer: str, sources: list):
        """Lưu đoạn chat vào DB (Background Task)"""
        try:
            # Convert sources list sang JSON string
            sources_json = json.dumps(sources, ensure_ascii=False)
            
            stmt = insert(chat_history).values(
                user_id=user_id,
                question=question,
                answer=answer,
                sources=sources_json
            )
            
            # Dùng self.db_session thay vì self.db
            self.db_session.execute(stmt)
            self.db_session.commit()
            print(f"📝 [History] Saved chat for User ID {user_id}")
            
        except Exception as e:
            print(f"❌ [History Error] Failed to save: {e}")
            # Rollback trên session
            self.db_session.rollback() 
        finally:
            # Quan trọng: Đóng session vì đây là thread riêng (Background Task)
            self.db_session.close()

    def get_user_history(self, user_id: int, limit: int = 20, offset: int = 0):
        """Lấy lịch sử chat"""
        query = (
            select(chat_history)
            .where(chat_history.c.user_id == user_id)
            .order_by(desc(chat_history.c.created_at))
            .limit(limit)
            .offset(offset)
        )
        # Dùng self.db_session
        result = self.db_session.execute(query).mappings().all()
        return result

    def clear_user_history(self, user_id: int):
        """Xóa lịch sử"""
        stmt = delete(chat_history).where(chat_history.c.user_id == user_id)
        result = self.db_session.execute(stmt)
        self.db_session.commit()
        return result.rowcount