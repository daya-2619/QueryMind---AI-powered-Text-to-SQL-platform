import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Text-to-SQL Analytics Platform"
    API_V1_STR: str = "/api/v1"
    
    # JWT Authentication
    SECRET_KEY: str = "SUPER_SECRET_SECURITY_KEY_CHANGE_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Metadata Database Connection (Platform DB)
    # Default to SQLite for easy local bootstrapping, can override to PostgreSQL URL
    METADATA_DATABASE_URL: str = "sqlite:///./metadata.db"
    
    # Target Database Connection (The DB we run queries against)
    # Default to a local PostgreSQL or sqlite
    TARGET_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ecommerce_db"
    
    # LLM Settings
    LLM_PROVIDER: str = "local"
    
    # Schema RAG and Vector DB Settings
    EMBEDDINGS_PROVIDER: str = "local"  # "local" (sentence-transformers), "openai", "gemini"
    EMBEDDINGS_MODEL_NAME: str = "all-MiniLM-L6-v2"
    VECTOR_DB_PATH: str = "./faiss_index"
    MAX_RELEVANT_TABLES: int = 6
    SIMILARITY_THRESHOLD: float = 0.3
    
    # Query Settings
    MAX_ROWS_LIMIT: int = 1000
    QUERY_TIMEOUT_SECONDS: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
