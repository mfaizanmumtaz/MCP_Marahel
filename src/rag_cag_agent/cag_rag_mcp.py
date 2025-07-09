import json
from sqlalchemy import select
from langchain_postgres.vectorstores import PGVector


from rag_cag_agent.database.connection import get_db
from rag_cag_agent.database.models import Collections_Dev, ChatHistory, RawData
from rag_cag_agent.utils.uuid_validater import validate_uuid
from langchain_openai import OpenAIEmbeddings

# Optional import for Qdrant - fallback if not available
from rag_cag_agent.database.qdrant_class import QdrantInsertRetrievalAll

qdrant = QdrantInsertRetrievalAll()

from langchain_core.documents import Document
from fastapi import status
from rag_cag_agent.utils.arbic_bot_utils import get_response
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from fastapi import HTTPException
from rag_cag_agent.config.settings import settings


class KnowledgeBase:
    def __init__(self, chatbot_id: str, user_id: str):
        self.chatbot_id = chatbot_id
        self.user_id = user_id
        
    async def get_knowledge_base(self, query_user: str):
        """Tool to search through the stored knowledge base to find the most relevant information 
        that matches the user's query. This tool uses advanced embedding models to find semantically 
        similar content and handles both English and Arabic queries. It takes into account the user's 
        chat history and returns well-formatted responses. Always use this tool when you cannot answer a question with your other existing tools.when user ask any question and you thought you cannot answer,please use this tool to get the knowledge base answer.just put the same user query in the tool call and you will get the appropriate answer.
        
        Args:
            query_user (str): The user's question or query to search for in the knowledge base. 
                            Examples: 'What is this document about?', 'Tell me about the company policies', 
                            'How does this system work?'
        
        Returns:
            Relevant final answer from the knowledge base that matches the user's query.
        """

        # Validate chatbot_id
        if not validate_uuid(self.chatbot_id):
            return {"error": "Invalid chatbot_id uuid format.", "status": "error"}

        db_generator = get_db()
        db = await db_generator.__anext__()
        try:
            # Fetch collection metadata
            stmt = select(Collections_Dev).filter_by(chatbot_id=self.chatbot_id)
            result = await db.execute(stmt)
            collection = result.scalar_one_or_none()

            if not collection:
                return {"error": "Collection not found", "status": "error"}

            llm_type = collection.llm

            # Get chat history
            history_query = (
                select(ChatHistory)
                .filter_by(chatbot_id=self.chatbot_id, user_id=self.user_id)
                .order_by(ChatHistory.id.desc())
                .limit(30)
            )
            result = await db.execute(history_query)
            chat_history = result.scalars().all()

            embeddings_model = collection.embeddings_model
            vectorstore_name = collection.vectordb_name
            collection_ = collection.collection_name

            if embeddings_model == "openai":
                embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

            # Initialize LLM based on model type
            if llm_type == "openai":
                try:
                    llm_model = ChatOpenAI(
                        temperature=0,
                        model=settings.OPENAI_MODEL,
                    )
                except Exception:
                    return {
                        "error": "Error initializing OpenAI LLM. Please set the model name in the .env file.",
                        "status": "error",
                    }

            elif llm_type == "claude":
                try:
                    llm_model = ChatAnthropic(
                        model_name=settings.CLAUDE_MODEL,
                        timeout=30
                    )
                except Exception:
                    return {
                        "error": "Error initializing Claude LLM. Please check the model configuration.",
                        "status": "error",
                    }
            else:
                return {
                    "error": "Invalid LLM model; please pass either openai, claude, or cohere.",
                    "status": "error",
                }

            # Retrieval from vector store or DB
            if vectorstore_name == "pgvector":
                vector_store = PGVector(
                    embeddings=embeddings,
                    collection_name=collection_,
                    connection=settings.PGVECTOR_CONNECTION,
                    use_jsonb=True,
                    async_mode=True,
                )
                results, source = await get_response(
                    query_user, vector_store, chat_history, None, llm_model
                )

            elif vectorstore_name == "qdrant":
                if qdrant:
                    vector_store = await qdrant.retrieval(
                        collection_name=collection_, embeddings=embeddings
                    )
                    results, source = await get_response(
                        query_user, vector_store, chat_history, None, llm_model
                    )
                else:
                    return {"error": "Qdrant is not available", "status": "error"}

            elif vectorstore_name == "postgres":
                # Fetch data with chatbot_id
                stmt = select(RawData).filter(RawData.chatbot_id == self.chatbot_id)
                result = await db.execute(stmt)
                raw_records = result.scalars().all()

                if not raw_records:
                    return {
                        "error": f"No data found for this chatbot_id: {self.chatbot_id}",
                        "status": "error",
                    }

                # Combine data from all records
                all_docs = []
                for record in raw_records:
                    raw_data = record.data
                    docs = [Document(**doc) for doc in json.loads(raw_data)]
                    all_docs.extend(docs)

                results, source = await get_response(
                    query_user, all_docs, chat_history, None, llm_model
                )

            else:
                return {
                    "error": "Could not find the vectorstore database",
                    "status": "error",
                }

            # Save history
            await self._save_history_in_background(
                query_user,
                results,
                collection.uuid,
            )

            # Commit the session
            await db.commit()

            return {
                "message": "Response Generated Successfully!",
                "data": {"response": results, "source": source},
                "status": "success",
            }

        except Exception as ex:
            await db.rollback()
            return {"error": f"An error occurred: {str(ex)}", "status": "error"}
        finally:
            await db.close()

    async def _save_history_in_background(
        self, query: str, response: str, collection_uuid: str
    ):
        db_generator = get_db()
        db = await db_generator.__anext__()
        try:
            new_history = ChatHistory(
                chatbot_id=self.chatbot_id,
                user_id=self.user_id,
                query=query,
                response=response,
                collection_uuid=collection_uuid,
            )
            db.add(new_history)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save chat history: {str(e)}",
            )
        finally:
            await db.close()
