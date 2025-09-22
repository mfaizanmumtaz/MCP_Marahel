import asyncio
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from translation.database.connection import async_engine as engine, Base


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
    content = Column(Text, nullable=False)
    pgvector_collection_name = Column(
        String(255), nullable=True
    )  # Store pgvector collection name
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
