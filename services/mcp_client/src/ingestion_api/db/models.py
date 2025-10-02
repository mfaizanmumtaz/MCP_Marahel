import asyncio
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, LargeBinary, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TEXT, UUID
from sqlalchemy.orm import relationship
from ingestion_api.db.connection import async_engine as engine, Base


class Collections_Dev(Base):
    __tablename__ = "collections_dev_2"

    uuid = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_name = Column(String, nullable=True)
    prompt = Column(Text, nullable=True)
    embeddings_model = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    chatbot_id = Column(
        String, nullable=False, unique=True
    )  # Enforced unique constraint
    vectordb_name = Column(String, nullable=False)
    llm = Column(String, nullable=False)


class ChatHistory(Base):
    __tablename__ = "chat_history_dev_2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_uuid = Column(String, nullable=False)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    chatbot_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)


class RawData(Base):
    __tablename__ = "raw_data_dev_2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    data = Column(TEXT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    chatbot_id = Column(String, nullable=False)
    session_id = Column(String, nullable=True)


class UserFile(Base):
    __tablename__ = "user_files_dev_2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    content = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    session_id = Column(String, nullable=True)


class LoanRecord(Base):
    __tablename__ = "loan_records_dev_2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    loan_record_data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    tenant_id = Column(String(255), ForeignKey('tenants.tenant_id', ondelete='CASCADE'), nullable=False)
    filename = Column(String(500), nullable=False)  # Original filename
    file_type = Column(String(50), nullable=False)  # pdf, docx, doc
    file_size_mb = Column(String(50), nullable=True)  # Original file size
    extraction_method = Column(String(100), nullable=False)  # ocr, text_extraction, docx_conversion
    processing_time_seconds = Column(String(50), nullable=True)  # Time taken to process
    content = Column(Text, nullable=False)  # JSON array of Document objects
    thumbnail_path = Column(String(500), nullable=True)  # Path to thumbnail image
    pdf_path = Column(String(500), nullable=True)  # Path to converted/compressed PDF (for DOCX conversions)
    pgvector_collection_name = Column(String(255), nullable=True)  # Store pgvector collection name
    page_count = Column(String(50), nullable=True)  # Number of pages
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to tenant
    tenant = relationship("Tenant", backref="documents", foreign_keys=[tenant_id])


class ModelPreference(Base):
    __tablename__ = "model_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(255),
        ForeignKey('tenants.tenant_id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )  # Foreign key to Tenant.tenant_id with cascade delete
    model_provider = Column(String(50), nullable=False)  # 'openai' or 'gemini'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())