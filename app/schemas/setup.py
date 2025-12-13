from pydantic import BaseModel, EmailStr
from typing import Optional

class FirstAdminRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = "System Administrator"

class AdminSetupConfig(BaseModel):
    admin_secret_key: str 

class NetworkConfig(BaseModel):
    api_base_url: str
    websocket_url: str

class DatabaseConfig(BaseModel):
    db_type: str = "PostgreSQL"
    host: str
    port: str
    username: str
    password: str
    db_name: str

class VectorConfig(BaseModel):
    provider: str = "Qdrant"
    host: str
    api_key: Optional[str] = None
    collection_name: str

class LLMConfig(BaseModel):
    provider: str = "Gemini"
    api_key: str
    model_name: str = "gemini-2.5-flash"

class GeneralConfig(BaseModel):
    bot_name: str
    welcome_message: str
    language: str = "Vietnamese"