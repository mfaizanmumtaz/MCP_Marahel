import asyncio
from langchain_postgres.vectorstores import PGVector
import os
from rag.database.connection import async_session
from sqlalchemy import text
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv,find_dotenv
load_dotenv(find_dotenv())
# import sys
# if sys.platform.startswith("win"):
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def pg_insertion(text, embeddings, collection_name):
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=os.getenv("pgvector_connection"),
        use_jsonb=True,
        async_mode=True,
    )
    _object = await vector_store.aadd_documents(text)
    return _object


embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

async def get_data(query, collection_name, user_id=None):
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=os.getenv("pgvector_connection"),
        use_jsonb=True,
        async_mode=True,
    )

    filter_dict = {}
    if user_id:
        filter_dict = {"user_id": user_id}

    _object = await vector_store.asimilarity_search(query=query, k=10, filter=filter_dict)

    print("retrival successful")
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

# async def main():
#     result = await get_data(query="hi", collection_name="pg_collection_250915_1305_LbCL0S_1122_Testuser_shared",user_id="hi")
#     print(result)

# asyncio.run(main())