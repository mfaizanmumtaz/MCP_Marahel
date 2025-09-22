from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from rag.config import settings

# SQLAlchemy Base
from sqlalchemy.orm import declarative_base
Base = declarative_base()

# Create async SQLAlchemy engine
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout
)

# Create synchronous engine
engine = create_engine(
    settings.sync_database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
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