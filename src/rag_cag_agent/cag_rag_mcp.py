import os
import sys
import json
from sqlalchemy import select, delete
from langchain_postgres.vectorstores import PGVector
from sqlalchemy.ext.asyncio import AsyncSession

# Add the project root to Python path

from rag_cag_agent.database.connection import async_session
from rag_cag_agent.database.models import Collections_Dev, ChatHistory, RawData, UserFile
from rag_cag_agent.utils.uuid_validater import validate_uuid
from langchain_openai import OpenAIEmbeddings

# Optional import for Qdrant - fallback if not available
from rag_cag_agent.database.qdrant_class import QdrantInsertRetrievalAll
qdrant = QdrantInsertRetrievalAll()

from langchain_core.documents import Document
from pydantic import BaseModel, Field
from typing import Optional, List
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import UploadFile, Form, status, Depends
from rag_cag_agent.utils.arbic_bot_utils import get_response
from rag_cag_agent.schemas.arbic_bot_schema import (
    QueryInput,
    DeleteCollectionInput,
    CustomInstructionInput,
)
import tempfile
import random
import datetime
from rag_cag_agent.prompts.generals_prompts import greeting_classifier_prompt
import string
from langchain_openai import ChatOpenAI
import ast
from langchain_core.prompts.chat import ChatPromptTemplate
from operator import itemgetter
from langchain_anthropic import ChatAnthropic
from rag_cag_agent.database.pg_vector import pg_insertion, pg_deletion
import aiofiles
import aiofiles.os
import asyncio
from fastapi import HTTPException
from rag_cag_agent.config.settings import settings
from langchain_core.tools import tool


class KnowledgeBase:
    def __init__(self, chatbot_id: str, user_id: str):
        self.chatbot_id = chatbot_id
        self.user_id = user_id
        self.db = None

    async def get_knowledge_base(self, query_user: str):
        """When user ask any question.you thought you cannot answer , this tool will be used to get the knowledge base from the database.
        This tool searches through the stored knowledge base to find the most relevant information
        that matches the user's query. It takes into account the user's chat history and uses 
        advanced embedding models to find semantically similar content. The tool handles both 
        English and Arabic queries and returns well-formatted responses.
        Example Query:
        Input: What this document is about?
        """
        
        try:
            self.db = async_session()
            
            # Validate chatbot_id
            if not validate_uuid(self.chatbot_id):
                return {
                    "error": "Invalid chatbot_id uuid format.",
                    "status": "error"
                }

            # Fetch collection metadata
            stmt = select(Collections_Dev).filter_by(chatbot_id=self.chatbot_id)
            result = await self.db.execute(stmt)
            collection = result.scalar_one_or_none()

            if not collection:
                return {
                    "error": "Collection not found",
                    "status": "error"
                }

            llm_type = collection.llm

            # Get chat history
            history_query = (
                select(ChatHistory)
                .filter_by(chatbot_id=self.chatbot_id, user_id=self.user_id)
                .order_by(ChatHistory.id.desc())
                .limit(30)
            )
            result = await self.db.execute(history_query)
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
                        openai_api_key=settings.OPENAI_API_KEY,
                    )
                except Exception as e:
                    return {
                        "error": "Error initializing OpenAI LLM. Please set the model name in the .env file.",
                        "status": "error"
                    }

            elif llm_type == "claude":
                llm_model = ChatAnthropic(
                    model=settings.CLAUDE_MODEL,
                    api_key=settings.CLAUDE_API_KEY
                )
            else:
                return {
                    "error": "Invalid LLM model; please pass either openai, claude, or cohere.",
                    "status": "error"
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
                    query_user,
                    vector_store,
                    chat_history,
                    None,
                    llm_model
                )

            elif vectorstore_name == "qdrant":
                if qdrant:
                    vector_store = await qdrant.retrieval(
                        collection_name=collection_, 
                        embeddings=embeddings
                    )
                    results, source = await get_response(
                        query_user,
                        vector_store,
                        chat_history,
                        None,
                        llm_model
                    )
                else:
                    return {
                        "error": "Qdrant is not available",
                        "status": "error"
                    }

            elif vectorstore_name == "postgres":
                # Fetch data with chatbot_id
                stmt = select(RawData).filter(RawData.chatbot_id == self.chatbot_id)
                result = await self.db.execute(stmt)
                raw_records = result.scalars().all()

                if not raw_records:
                    return {
                        "error": f"No data found for this chatbot_id: {self.chatbot_id}",
                        "status": "error"
                    }

                # Combine data from all records
                all_docs = []
                for record in raw_records:
                    raw_data = record.data
                    docs = [Document(**doc) for doc in json.loads(raw_data)]
                    all_docs.extend(docs)

                results, source = await get_response(
                    query_user, 
                    all_docs, 
                    chat_history, 
                    None,
                    llm_model
                )

            else:
                return {
                    "error": "Could not find the vectorstore database",
                    "status": "error"
                }

            # Save history
            await self._save_history_in_background(
                query_user,
                results,
                collection.uuid,
            )

            # Commit the session
            await self.db.commit()

            return {
                "message": "Response Generated Successfully!",
                "data": {"response": results, "source": source},
                "status": "success"
            }

        except Exception as ex:
            if self.db:
                await self.db.rollback()
            return {
                "error": f"An error occurred: {str(ex)}",
                "status": "error"
            }
        finally:
            if self.db:
                await self.db.close()

    async def _save_history_in_background(
        self,
        query: str,
        response: str,
        collection_uuid: str
    ):
        try:
            self.db = async_session()
            new_history = ChatHistory(
                chatbot_id=self.chatbot_id,
                user_id=self.user_id,
                query=query,
                response=response,
                collection_uuid=collection_uuid,
            )
            self.db.add(new_history)
            await self.db.commit()
        except Exception as e:
            if self.db:
                await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save chat history: {str(e)}"
            )
        finally:
            if self.db:
                await self.db.close()