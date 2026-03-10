from sqlalchemy import ForeignKey, Table, Column, Integer, String, Boolean, DateTime, Text, func
from app.db.base import metadata
# =====================================================
# CHAT & SYSTEM TABLES
# =====================================================

# 6. Bảng Chat Sessions (Quản lý luồng hội thoại)
chat_sessions = Table('chat_sessions', metadata,
    Column('id', String(36), primary_key=True), # UUID
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('title', String(255)), 
    Column('created_at', DateTime, server_default=func.now()),
    Column('updated_at', DateTime, server_default=func.now(), onupdate=func.now())
)

# 7. Bảng Chat History (Nội dung tin nhắn)
chat_history = Table('chat_history', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('session_id', String(36), ForeignKey('chat_sessions.id'), nullable=False),
    Column('question', Text, nullable=False),
    Column('answer', Text, nullable=False),
    Column('sources', Text, nullable=True), # Lưu JSON nguồn
    Column('created_at', DateTime, server_default=func.now())
)
