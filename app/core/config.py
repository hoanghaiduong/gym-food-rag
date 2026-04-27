from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Gym Food RAG"
    API_V1_STR: str = "/api/v1"

    ADMIN_SECRET_KEY: str = "gym-food-super-admin"
    SECRET_KEY: str = "gym-food-super-secret-key-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    GOOGLE_API_KEY: str = ""
    USE_LOCAL_EMBEDDING: bool = True
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    SPARSE_EMBEDDING_STRATEGY: str = "auto"
    SPARSE_HASH_DIM: int = 2000003
    SPARSE_USE_BIGRAMS: bool = True
    RETRIEVAL_RERANK_MAX_PASSAGE_LENGTH: int = 256
    RETRIEVAL_RERANK_WEIGHTS: str = "0.4,0.2,0.4"

    LLM_BACKEND: str = "ollama"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_RETRIES: int = 2
    GEMINI_RETRY_BASE_SECONDS: float = 2.0
    GEMINI_RETRY_MAX_SECONDS: float = 20.0
    GEMINI_QUOTA_COOLDOWN_SECONDS: int = 900
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_REQUEST_TIMEOUT_SECONDS: int = 600

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    COLLECTION_NAME: str = "gym_food_hybrid_v1"
    COLLECTION_NAME_ACTIVE: str = ""
    COLLECTION_NAME_NEXT: str = ""
    QDRANT_SPARSE_INDEX_ON_DISK: bool = True
    RETRIEVAL_OVERFETCH_MULTIPLIER: int = 4
    RETRIEVAL_PREFETCH_MULTIPLIER: int = 2
    RETRIEVAL_ENABLE_RERANK: bool = True
    RETRIEVAL_ENABLE_LLM_QUERY_REWRITE: bool = True
    RETRIEVAL_ENABLE_NATIVE_RERANK: bool = False
    RETRIEVAL_NATIVE_RERANK_TIMEOUT_SECONDS: int = 15
    RETRIEVAL_NATIVE_RERANK_MAX_DOCS: int = 6
    RETRIEVAL_NATIVE_RERANK_MAX_CHARS: int = 512
    RETRIEVAL_RERANK_CANDIDATES: int = 24

    DATABASE_URL: str | None = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "admin"
    POSTGRES_DB: str = "gym_food_db"

    PGADMIN_EMAIL: str = "admin@gymfood.com"
    PGADMIN_PASSWORD: str = "admin"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str | None = None
    EXACT_CACHE_TTL_SECONDS: int = 900
    WORKFLOW_STATE_TTL_SECONDS: int = 3600

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def serving_collection_name(self) -> str:
        return self.COLLECTION_NAME_ACTIVE or self.COLLECTION_NAME

    @property
    def reindex_target_collection_name(self) -> str:
        return self.COLLECTION_NAME_NEXT or self.COLLECTION_NAME

    @property
    def alias_mode_enabled(self) -> bool:
        return bool(self.COLLECTION_NAME_ACTIVE)


settings = Settings()
