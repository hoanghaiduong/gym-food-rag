from sqlalchemy import MetaData, Table, Column, Integer, String, Text, DateTime, func

# Metadata dùng chung cho toàn bộ hệ thống
metadata = MetaData()

# 1. Bảng Users
users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(50), unique=True, nullable=False),
    Column('password_hash', String(255), nullable=False),
    Column('role', String(20), default='user'),
    Column('created_at', DateTime, server_default=func.now())
)

# 2. Bảng Chat History
chat_history = Table('chat_history', metadata,
    Column('id', Integer, primary_key=True),
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