import json
import uuid
from sqlalchemy.orm import Session  # Import thêm Session để type hint
from sqlalchemy import func, insert, select, desc, delete, update
from app.db.schemas import chat_history,chat_sessions

class HistoryService:
    def __init__(self, db_session: Session): 
        self.db_session = db_session  # Lưu vào biến self.db_session

    # --- QUẢN LÝ SESSION ---
    def create_session(self, user_id: int, first_question: str):
        """Tạo cuộc hội thoại mới"""
        session_id = str(uuid.uuid4())
        # Lấy 50 ký tự đầu của câu hỏi làm tiêu đề
        title = first_question[:50] + "..." if len(first_question) > 50 else first_question
        
        stmt = insert(chat_sessions).values(
            id=session_id,
            user_id=user_id,
            title=title
        )
        self.db_session.execute(stmt)
        self.db_session.commit()
        return session_id
    def get_user_sessions(self, user_id: int, limit: int = 20, offset: int = 0):
        """Lấy danh sách các cuộc hội thoại (cho Sidebar)"""
        query = (
            select(chat_sessions)
            .where(chat_sessions.c.user_id == user_id)
            .order_by(desc(chat_sessions.c.updated_at)) # Mới nhất lên đầu
            .limit(limit)
            .offset(offset)
        )
        return self.db_session.execute(query).mappings().all()
    
    def get_session_messages(self, session_id: str, user_id: int):
        """Lấy chi tiết tin nhắn trong 1 hội thoại"""
        # Cần verify user_id để không xem trộm chat người khác
        # 1. Verify session owner
        check = self.db_session.execute(
            select(chat_sessions).where(chat_sessions.c.id == session_id, chat_sessions.c.user_id == user_id)
        ).fetchone()
        if not check:
            return None

        # 2. Get messages
        query = (
            select(chat_history)
            .where(chat_history.c.session_id == session_id)
            .order_by(chat_history.c.created_at.asc()) # Cũ trước, mới sau (để render từ trên xuống)
        )
        rows = self.db_session.execute(query).mappings().all()
        
        # Convert sang format User/Assistant để frontend dễ render
        messages = []
        for row in rows:
            messages.append({"role": "user", "content": row.question, "created_at": row.created_at})
            messages.append({"role": "assistant", "content": row.answer, "created_at": row.created_at})
            
        return messages

    def update_session_time(self, session_id: str):
        """Cập nhật thời gian updated_at để session này nhảy lên đầu list"""
        stmt = update(chat_sessions).where(chat_sessions.c.id == session_id).values(updated_at=func.now())
        self.db_session.execute(stmt)
        self.db_session.commit()
        
    async def save_interaction(self, user_id: int, session_id: str, question: str, answer: str, sources: list):
        try:
            sources_json = json.dumps(sources, ensure_ascii=False)
            stmt = insert(chat_history).values(
                user_id=user_id,
                session_id=session_id, # [MỚI]
                question=question,
                answer=answer,
                sources=sources_json
            )
            self.db_session.execute(stmt)
            
            # Update thời gian session
            self.update_session_time(session_id)
            
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            print(f"❌ Save History Error: {e}")
        finally:
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