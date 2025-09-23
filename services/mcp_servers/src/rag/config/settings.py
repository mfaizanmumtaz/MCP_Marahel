import os
import sys
import asyncio
from urllib.parse import quote
from dotenv import load_dotenv, find_dotenv
from typing import Optional

# Load environment variables
load_dotenv(find_dotenv())


class Settings:
    """Centralized settings and configuration management for RAG module."""

    def __init__(self):
        # Fix for Windows asyncio compatibility with psycopg
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Database Configuration
    @property
    def pg_user_name(self) -> str:
        return os.getenv("PG_USER_NAME", "")

    @property
    def pg_password(self) -> str:
        return os.getenv("PG_PASSWORD", "")

    @property
    def pg_host(self) -> str:
        return os.getenv("PG_HOST", "localhost")

    @property
    def pg_port(self) -> str:
        return os.getenv("PG_PORT", "5432")

    @property
    def pg_name(self) -> str:
        return os.getenv("PG_NAME", "")

    @property
    def database_url(self) -> str:
        """Async PostgreSQL database URL with asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.pg_user_name}:{quote(self.pg_password)}@"
            f"{self.pg_host}:{self.pg_port}/{self.pg_name}"
        )

    @property
    def sync_database_url(self) -> str:
        """Synchronous PostgreSQL database URL."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql")

    @property
    def pgvector_connection(self) -> str:
        """PGVector connection string - fallback to legacy env var if available."""
        return os.getenv("pgvector_connection") or self.database_url

    # Database Pool Configuration
    @property
    def db_pool_size(self) -> int:
        return int(os.getenv("DB_POOL_SIZE", "500"))

    @property
    def db_max_overflow(self) -> int:
        return int(os.getenv("DB_MAX_OVERFLOW", "500"))

    @property
    def db_pool_timeout(self) -> int:
        return int(os.getenv("DB_POOL_TIMEOUT", "60"))

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "true").lower() == "true"

    # OpenAI Configuration
    @property
    def openai_api_key(self) -> Optional[str]:
        return os.getenv("OPENAI_API_KEY")

    @property
    def openai_embedding_model(self) -> str:
        return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    @property
    def openai_chat_model(self) -> str:
        return os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")

    @property
    def openai_temperature(self) -> float:
        return float(os.getenv("OPENAI_TEMPERATURE", "0.5"))

    # Vector Search Configuration
    @property
    def vector_search_k(self) -> int:
        """Number of vectors to retrieve in similarity search."""
        return int(os.getenv("VECTOR_SEARCH_K", "10"))
    
    @property
    def OPENAI_TEMPERATURE(self) -> float:
        return float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
    
    @property
    def OPENAI_MODEL(self) -> str:
        return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    @property
    def OPENROUTER_API_KEY(self) -> str:
        return os.getenv("OPENROUTER_API_KEY", "")

    @property
    def OPENROUTER_BASE_URL(self) -> str:
        return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Create global settings instance
settings = Settings()