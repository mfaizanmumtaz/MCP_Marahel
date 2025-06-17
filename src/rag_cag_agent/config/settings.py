from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv,find_dotenv
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
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")
    
    # Anthropic Settings
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    
    # Qdrant Settings
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    
    # PlayHT Settings
    PLAYHT_API_KEY: str = os.getenv("PLAYHT_API_KEY", "")
    PLAYHT_USER_ID: str = os.getenv("PLAYHT_USER_ID", "")
    
    # Server Settings
    MCP_HOST: str = os.getenv("MCP_HOST", "0.0.0.0")
    MCP_PORT: int = int(os.getenv("MCP_PORT", "8050"))
    
    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_DIR: str = os.getenv("LOG_DIR", "log/ai")
    
    class Config:
        case_sensitive = True

# Create a global settings instance
settings = Settings() 