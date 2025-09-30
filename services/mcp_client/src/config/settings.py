from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv, find_dotenv
from urllib.parse import quote

load_dotenv(find_dotenv())


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MCP Client Supervisor Agent"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

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
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # Anthropic Settings
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

    # LangSmith Settings
    LANGSMITH_TRACING: str = os.getenv("LANGCHAIN_TRACING", "false")
    LANGSMITH_ENDPOINT: str = os.getenv("LANGCHAIN_ENDPOINT", "")
    LANGSMITH_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGSMITH_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "")

    # Qdrant Settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

    # MCP Server Settings
    MCP_SERVER_HOST: str = os.getenv("MCP_SERVER_HOST", "localhost")
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8001"))
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:9697/mcp")

    # MCP Client Robustness Settings
    MCP_MAX_RETRIES: int = int(os.getenv("MCP_MAX_RETRIES", "3"))
    MCP_RETRY_DELAY: float = float(os.getenv("MCP_RETRY_DELAY", "1.0"))
    MCP_BACKOFF_FACTOR: float = float(os.getenv("MCP_BACKOFF_FACTOR", "2.0"))
    MCP_TIMEOUT: float = float(os.getenv("MCP_TIMEOUT", "30.0"))
    MCP_HEALTH_CHECK_INTERVAL: float = float(os.getenv("MCP_HEALTH_CHECK_INTERVAL", "60.0"))

    # Document Processing Settings
    CHUNK_SIZE: int = int(os.getenv("chunk_size", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("chunk_overlap", "300"))

    # Additional API Keys
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # Legacy property for backward compatibility
    @property
    def PGVECTOR_CONNECTION_LEGACY(self) -> str:
        return f"postgresql://{self.PG_USER_NAME}:{quote(self.PG_PASSWORD)}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_NAME}?sslmode=disable"

    # Google Settings
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
    GOOGLE_CACHE_TTL: int = int(os.getenv("GOOGLE_CACHE_TTL", "3600"))  # Cache TTL in seconds (default 1 hour)

    class Config:
        case_sensitive = True


# Create a global settings instance
settings = Settings()