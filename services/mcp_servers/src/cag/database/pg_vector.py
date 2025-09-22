from langchain_postgres.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
from cag.config.settings import settings

embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_MODEL)

async def get_data(query, collection_name, user_id=None):
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=settings.DATABASE_URL,
        use_jsonb=True,
        async_mode=True,
    )

    filter_dict = {}
    if user_id:
        filter_dict = {"user_id": user_id}

    _object = await vector_store.asimilarity_search(query=query, k=10, filter=filter_dict)

    return _object


