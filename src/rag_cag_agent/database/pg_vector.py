from langchain_postgres.vectorstores import PGVector
import os
from rag_cag_agent.database.connection import async_session
from sqlalchemy import text

from dotenv import load_dotenv

load_dotenv()


async def pg_insertion(text, embeddings, collection_name):
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=os.getenv("pgvector_connection"),
        use_jsonb=True,
        async_mode=True,
    )
    _object = await vector_store.aadd_documents(text)

    print("insertion successful")
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
