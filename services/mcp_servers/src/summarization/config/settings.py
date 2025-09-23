import os
import sys
import asyncio
from urllib.parse import quote
from dotenv import load_dotenv, find_dotenv
from typing import Optional

# Load environment variables
load_dotenv(find_dotenv())


class Settings:
    """Centralized settings and configuration management for Summarization module."""

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
    def DATABASE_URL(self) -> str:
        """Async PostgreSQL database URL with asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.pg_user_name}:{quote(self.pg_password)}@"
            f"{self.pg_host}:{self.pg_port}/{self.pg_name}"
        )

    @property
    def sync_database_url(self) -> str:
        """Synchronous PostgreSQL database URL."""
        return self.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")

    # Database Pool Configuration
    @property
    def DB_POOL_SIZE(self) -> int:
        return int(os.getenv("DB_POOL_SIZE", "500"))

    @property
    def DB_MAX_OVERFLOW(self) -> int:
        return int(os.getenv("DB_MAX_OVERFLOW", "500"))

    @property
    def DB_POOL_TIMEOUT(self) -> int:
        return int(os.getenv("DB_POOL_TIMEOUT", "60"))

    @property
    def db_echo(self) -> bool:
        return os.getenv("DB_ECHO", "true").lower() == "true"

    # OpenAI Configuration
    @property
    def openai_api_key(self) -> Optional[str]:
        return os.getenv("OPENAI_API_KEY")

    @property
    def openai_summarization_model(self) -> str:
        return os.getenv("OPENAI_SUMMARIZATION_MODEL", "gpt-4o-mini")

    @property
    def openai_temperature(self) -> float:
        return float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    

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