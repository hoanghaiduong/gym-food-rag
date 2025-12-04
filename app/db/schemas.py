from sqlalchemy import MetaData, Table, Column, Integer, String, Text, DateTime, Boolean, func, ForeignKey

# Metadata dùng chung cho toàn bộ hệ thống
metadata = MetaData()

# 1. Bảng Users (Core)
users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(50), unique=True, nullable=False),
    Column('email', String(100), unique=True, nullable=False),
    Column('password_hash', String(255), nullable=False),
    Column('full_name', String(100), nullable=True),
    Column('is_active', Boolean, default=True),
    Column('refresh_token', String(500), nullable=True),
    Column('created_at', DateTime, server_default=func.now())
)

# =====================================================
# RBAC TABLES (HỆ THỐNG PHÂN QUYỀN MỚI - V3)
# =====================================================

# 2. Bảng Permissions (Quyền hạn nhỏ nhất)
permissions = Table('permissions', metadata,
    Column('id', Integer, primary_key=True),
    Column('slug', String(100), unique=True, nullable=False), # VD: 'food:create'
    Column('name', String(255)),
    Column('description', Text)
)

# 3. Bảng Roles (Nhóm quyền)
roles = Table('roles', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(50), unique=True, nullable=False), # VD: 'Admin', 'Editor'
    Column('description', Text)
)

# 4. Bảng liên kết Role - Permission
role_permissions = Table('role_permissions', metadata,
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True)
)

# 5. Bảng liên kết User - Role
user_roles = Table('user_roles', metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)

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

# 8. Bảng System Settings (Cấu hình động)
system_settings = Table('system_settings', metadata,
    Column('key', String(50), primary_key=True),
    Column('value', Text),
    Column('updated_at', DateTime, server_default=func.now(), onupdate=func.now())
)