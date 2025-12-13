# app/db/tables/rbac.py
from sqlalchemy import Table, Column, Integer, String, Text, ForeignKey
from app.db.base import metadata  # <-- Import metadata từ base

# 1. Bảng Permissions
permissions = Table('permissions', metadata,
    Column('id', Integer, primary_key=True),
    Column('slug', String(100), unique=True, nullable=False),
    Column('name', String(255)),
    Column('description', Text)
)

# 2. Bảng Roles
roles = Table('roles', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(50), unique=True, nullable=False),
    Column('description', Text)
)

# 3. Các bảng liên kết (role_permissions, user_roles)...
role_permissions = Table('role_permissions', metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete="CASCADE"), primary_key=True)
)

user_roles = Table('user_roles', metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True)
)