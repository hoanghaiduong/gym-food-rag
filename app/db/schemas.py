from sqlalchemy import Boolean, ForeignKey, MetaData, Table, Column, Integer, String, Text, DateTime, func

# Metadata dùng chung cho toàn bộ hệ thống
metadata = MetaData()
# 1. Bảng Users (Không thay đổi nhiều)
users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(50), unique=True, nullable=False),
    Column('email', String(100), unique=True, nullable=False),
    Column('password_hash', String(255), nullable=False),
    Column('full_name', String(100), nullable=True),
    Column('role', String(20), default='user'),
    Column('is_active', Boolean, default=True), # Dùng Boolean chuẩn của SQLAlchemy
    Column('refresh_token', String(500), nullable=True),
    Column('created_at', DateTime, server_default=func.now())
)

# 2. Bảng Chat History (Đã bổ sung mối quan hệ)
chat_history = Table('chat_history', metadata,
    Column('id', Integer, primary_key=True),
    # [FIX & BỔ SUNG] Khóa ngoại liên kết tới cột users.id
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False), 
    Column('question', Text, nullable=False),
    Column('answer', Text, nullable=False),
    Column('created_at', DateTime, server_default=func.now())
)

# 3. Bảng System Settings
system_settings = Table('system_settings', metadata,
    Column('key', String(50), primary_key=True),
    Column('value', Text),
    Column('updated_at', DateTime, server_default=func.now(), onupdate=func.now())
)
