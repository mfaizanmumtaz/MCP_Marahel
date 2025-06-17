from qdrant_client import QdrantClient, models, AsyncQdrantClient
from langchain_qdrant import QdrantVectorStore
import os
from dotenv import load_dotenv
import warnings

warnings.filterwarnings("ignore")
load_dotenv()
# Initialize environment and qdrant
qdrant_api_key = os.getenv("QDRANT_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")


class QdrantInsertRetrievalAll:
    def __init__(self):
        self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.async_client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    # Method to insert documents into Qdrant vector store
    async def insertion(self, text, embeddings, collection_name):
        qdrant = QdrantVectorStore.from_documents(
            text,
            embeddings,
            url=qdrant_url,
            api_key=qdrant_api_key,
            prefer_grpc=True,
            collection_name=collection_name,
        )
        return qdrant

    # Method to retrieve documents from Qdrant vector store
    async def retrieval(self, collection_name, embeddings):
        # Create vector store with async client
        qdrant_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=collection_name,
            embedding=embeddings,
        )
        return qdrant_store

    # Method to delete a collection from Qdrant
    async def delete_collection(self, collection_name):
        await self.async_client.delete_collection(collection_name)
        return collection_name

    # Method to create a new collection in Qdrant with cosine similarity
    async def create_collection(self, collection_name):
        await self.async_client.create_collection(
            collection_name,
            vectors_config=models.VectorParams(
                size=100, distance=models.Distance.COSINE
            ),
        )
        return collection_name
