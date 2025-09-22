from langchain_postgres.vectorstores import PGVector
import os
import asyncio
from ingestion_api.db.connection import async_session
from sqlalchemy import text
from config.settings import settings


async def pg_insertion(docs, embeddings, collection_name, user_id=None):
    if user_id:
        for doc in docs:
            doc.metadata["user_id"] = user_id

    # Use synchronous connection string for pgvector (langchain-postgres requirement)
    sync_connection = settings.PGVECTOR_CONNECTION_LEGACY

    def _sync_insertion():
        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=sync_connection,
            use_jsonb=True,
        )
        return vector_store.add_documents(docs)

    # Run synchronous operation in thread pool to avoid blocking async event loop
    _object = await asyncio.get_event_loop().run_in_executor(None, _sync_insertion)

    return _object


async def pg_deletion(name):
    async with async_session() as session:
        try:
            # Delete related rows from langchain_pg_embedding
            delete_embeddings_query = text("""
                DELETE FROM langchain_pg_embedding
                WHERE collection_id IN (
                    SELECT uuid FROM langchain_pg_collection
                    WHERE name = :collection_name
                )
            """)
            await session.execute(delete_embeddings_query, {"collection_name": name})

            # Delete rows from langchain_pg_collection
            delete_collection_query = text("""
                DELETE FROM langchain_pg_collection
                WHERE name = :collection_name
            """)
            await session.execute(delete_collection_query, {"collection_name": name})

            # Commit the transaction
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
