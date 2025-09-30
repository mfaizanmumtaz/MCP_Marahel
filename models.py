# import asyncio
# import uuid
# from datetime import datetime
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# from sqlalchemy.orm import sessionmaker, declarative_base
# from sqlalchemy import create_engine
# from sqlalchemy import Column, String, Text, DateTime, Boolean
# from sqlalchemy.dialects.postgresql import UUID
# from dotenv import load_dotenv
# load_dotenv()
# import os

# # Create the Base class
# Base = declarative_base()

# PG_HOST= "158.101.247.161"
# PG_NAME= "morshed_db"
# PG_USER_NAME= "postgres"
# PG_PASSWORD= "asdfghjkertyuiocvbnm"
# PG_PORT= "5432"

# async_engine = create_async_engine(
#     f"postgresql+asyncpg://{PG_USER_NAME}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_NAME}",
#     echo=True,
# ) 

# class Tenant(Base):
#     __tablename__ = "tenants"

#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     tenant_id = Column(
#         String(255), nullable=False, unique=True
#     )  # Unique tenant identifier
#     user_id = Column(String(255), nullable=True)  # Optional user_id
#     summary_access = Column(Boolean, default=False)
#     translation_access = Column(Boolean, default=False)
#     rag_access = Column(Boolean, default=False)
#     cag_access = Column(Boolean, default=False)
#     created_at = Column(DateTime, default=datetime.utcnow)


# class KnowledgeBase(Base):
#     __tablename__ = "knowledge_base"

#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     tenant_id = Column(String(255), nullable=False)
#     user_id = Column(
#         String(255), nullable=True
#     )  # Optional user isolation within tenant
#     content = Column(Text, nullable=False)
#     pgvector_collection_name = Column(
#         String(255), nullable=True
#     )  # Store pgvector collection name
#     created_at = Column(DateTime, default=datetime.utcnow)


# class ModelPreference(Base):
#     __tablename__ = "model_preferences"

#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     tenant_id = Column(String(255), nullable=False, unique=True)  # One preference per tenant
#     model_provider = Column(String(50), nullable=False)  # 'openai' or 'gemini'
#     created_at = Column(DateTime, default=datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# async def init_db():
#     """Initialize database tables."""
#     async with async_engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)


# if __name__ == "__main__":
#     asyncio.run(init_db())


from langchain_google_genai import ChatGoogleGenerativeAI
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash",google_api_key="AIzaSyCgS-cgm_OvDDpWF2cVMh9yPOTTHiAWif0")
response = model.invoke("Hello, world!")
print(response)