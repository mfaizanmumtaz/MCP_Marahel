from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv, find_dotenv
from urllib.parse import quote

load_dotenv(find_dotenv())


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "CAG RAG MCP Marahel"

    # CORS Settings
    BACKEND_CORS_ORIGINS: list = ["*"]

    # Database Settings
    PG_USER_NAME: str = os.getenv("PG_USER_NAME", "")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "")
    PG_HOST: str = os.getenv("PG_HOST", "localhost")
    PG_PORT: str = os.getenv("PG_PORT", "5432")
    PG_NAME: str = os.getenv("PG_NAME", "")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.PG_USER_NAME}:{quote(self.PG_PASSWORD)}@"
            f"{self.PG_HOST}:{self.PG_PORT}/{self.PG_NAME}"
        )

    @property
    def PGVECTOR_CONNECTION(self) -> str:
        return self.DATABASE_URL

    # Database Pool Settings
    DB_POOL_SIZE: int = 500
    DB_MAX_OVERFLOW: int = 500
    DB_POOL_TIMEOUT: int = 60

    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    OPENAI_TEMPERATURE: float = os.getenv("OPENAI_TEMPERATURE", 0.1)
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # Anthropic Settings
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    class Config:
        case_sensitive = True


# Create a global settings instance
settings = Settings()