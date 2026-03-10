
from sqlalchemy import Column, String, Table, Text,DateTime,func
from app.db.tables import metadata  # Đảm bảo đúng tên file schema của bạn


system_settings = Table('system_settings', metadata,
    Column('key', String(50), primary_key=True),
    Column('value', Text),
    Column('updated_at', DateTime, server_default=func.now(), onupdate=func.now())
)