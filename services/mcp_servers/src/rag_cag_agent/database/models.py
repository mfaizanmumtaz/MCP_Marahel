from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.postgresql import TEXT
from urllib.parse import quote
import uuid
import os
from datetime import datetime
from sqlalchemy import LargeBinary
import asyncio
import sys

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


class GoogleSheet(Base):
    __tablename__ = "google_sheets_dev_2"
    uuid = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chatbot_id = Column(String, nullable=False, unique=True)
    content = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


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
