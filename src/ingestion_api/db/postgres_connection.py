import os
import sys
import asyncio
from dotenv import load_dotenv, find_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

load_dotenv(find_dotenv())

# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

pgvector_connection = os.getenv("pgvector_connection")
if not pgvector_connection:
    raise ValueError("pgvector_connection environment variable is required")

# Create async SQLAlchemy engine
async_engine = create_async_engine(pgvector_connection)

# Create synchronous engine
engine = create_engine(
    pgvector_connection.replace("postgresql+asyncpg", "postgresql"),
    pool_size=500,
    max_overflow=500,
    pool_timeout=60,
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
