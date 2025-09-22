from langchain_postgres.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
from rag.database.connection import async_engine
from rag.config import settings
from sqlalchemy import text

embeddings = OpenAIEmbeddings(model=settings.openai_embedding_model)

async def get_data(query, collection_name, user_id=None):
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=settings.pgvector_connection,
        use_jsonb=True,
        async_mode=True,
    )

    filter_dict = {}
    if user_id:
        filter_dict = {"user_id": user_id}

    docs = await vector_store.asimilarity_search(query=query, k=settings.vector_search_k, filter=filter_dict)
    return docs