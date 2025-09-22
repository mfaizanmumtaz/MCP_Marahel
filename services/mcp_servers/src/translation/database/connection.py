from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from translation.config.settings import settings

# SQLAlchemy Base
Base = declarative_base()

# Create async SQLAlchemy engine
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT
)

# Create synchronous engine
engine = create_engine(
    settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql"),
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)

# Create async sessionmaker
async_session = sessionmaker(
    class_=AsyncSession, autocommit=False, autoflush=False, bind=async_engine
)


# Async dependency to get DB session
async def get_db():
    async with async_session() as db:
        try:
            yield db
        finally:
            await db.close()