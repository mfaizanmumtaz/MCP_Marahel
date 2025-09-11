from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import TEXT
from urllib.parse import quote
import uuid
import os
from datetime import datetime
from sqlalchemy import LargeBinary
import asyncio
import sys
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Database URL configuration
DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('PG_USER_NAME')}:{quote(os.getenv('PG_PASSWORD', ''))}@"
    f"{os.getenv('PG_HOST')}:{int(os.getenv('PG_PORT', '5432'))}/{os.getenv('PG_NAME')}"
)

# Async engine and session setup
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


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
    # session_id = Column(String,nullable=True)


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
    chatbot_id = Column(String, nullable=False)  # Enforced unique constraint

    session_id = Column(String, nullable=True)


class UserFile(Base):
    __tablename__ = "user_files_dev_2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = Column(String, nullable=False)  # Can be linked to chatbot_id/user_id
    filename = Column(String, nullable=False)
    content = Column(
        LargeBinary, nullable=False
    )  # This supports binary Excel/CSV files
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    session_id = Column(String, nullable=True)


class LoanRecord(Base):
    __tablename__ = "loan_records_dev_2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    loan_record_data = Column(Text, nullable=False)  # Store the raw string data
    created_at = Column(DateTime, default=datetime.utcnow)


class Tenant(Base):
    __tablename__ = 'tenants'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(255), nullable=False, unique=True)  # Unique tenant identifier
    user_id = Column(String(255), nullable=True)  # Optional user_id
    summary_access = Column(Boolean, default=False)
    translation_access = Column(Boolean, default=False)
    rag_access = Column(Boolean, default=False)
    cag_access = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    knowledge_bases = relationship("KnowledgeBase", back_populates="tenant")

class KnowledgeBase(Base):
    __tablename__ = 'knowledge_base'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)
    user_id = Column(String(255), nullable=True)  # Optional user isolation within tenant
    # file_name = Column(String(255), nullable=False)
    # file_type = Column(String(10), nullable=False)  # pdf, docx, txt, csv, xlsx
    content = Column(Text, nullable=False)
    pgvector_collection_name = Column(String(255), nullable=True)  # Store pgvector collection name
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="knowledge_bases")


# async def init_db():
#     # Create tables if not exist
#     async with engine.begin() as conn:in z
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
