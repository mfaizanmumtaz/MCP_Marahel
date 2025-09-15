from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote
import uuid
import os
from datetime import datetime
import asyncio
import sys
from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import UUID
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Database URL configuration
DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('PG_USER_NAME')}:{quote(os.getenv('PG_PASSWORD', ''))}@"
    f"{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_NAME')}"
)

# Async engine and session setup
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(255), nullable=False, unique=True
    )  # Unique tenant identifier
    user_id = Column(String(255), nullable=True)  # Optional user_id
    summary_access = Column(Boolean, default=False)
    translation_access = Column(Boolean, default=False)
    rag_access = Column(Boolean, default=False)
    cag_access = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(255), nullable=False)
    user_id = Column(
        String(255), nullable=True
    )  # Optional user isolation within tenant
    # file_name = Column(String(255), nullable=False)
    # file_type = Column(String(10), nullable=False)  # pdf, docx, txt, csv, xlsx
    content = Column(Text, nullable=False)
    pgvector_collection_name = Column(
        String(255), nullable=True
    )  # Store pgvector collection name
    created_at = Column(DateTime, default=datetime.utcnow)


# async def init_db():
#     # Create tables if not exist
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     print("Tables created successfully.")


# async def init_db():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.drop_all)
#         await conn.run_sync(Base.metadata.create_all)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
