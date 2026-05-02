# app/db/tables/__init__.py

# Import metadata
from app.db.base import metadata

# Import từng bảng vào đây để expose ra ngoài
from .users import users
from .rbac import roles, permissions, role_permissions, user_roles
from .chat import chat_sessions, chat_history
from .otp_requests import otp_requests
from .system_settings import system_settings
# from .products import products, orders
# ...

# List các biến public (Optional nhưng tốt cho IDE)
__all__ = [
    "metadata",
    "users",
    "roles", "permissions", "role_permissions", "user_roles",
    "otp_requests",
    "chat_sessions", "chat_history",
    "system_settings",
    # "products", "orders"
]
