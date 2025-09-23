from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from rag.database.pg_vector import get_data
from rag.database.connection import get_db
from rag.database.models import Tenant, KnowledgeBase
from rag.prompts import system_prompt_for_rag_based_generation
from rag.config.settings import settings
import json
import logging
from sqlalchemy import select
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("RAG KnowledgeBase")

# Initialize LLM with settings
# llm = ChatOpenAI(
#     model=settings.openai_chat_model,
#     api_key=settings.openai_api_key,
#     temperature=settings.openai_temperature
# )

llm = ChatOpenAI(
  api_key=settings.OPENROUTER_API_KEY,
  base_url=settings.OPENROUTER_BASE_URL,
  model=settings.OPENAI_MODEL,
  temperature=settings.OPENAI_TEMPERATURE)

async def get_answer(query,docs):
    prompt = ChatPromptTemplate([
        ("system", system_prompt_for_rag_based_generation),
        ("user", "{query}")
    ])
    chain = prompt | llm
    response = await chain.ainvoke({"query": query, "context": docs})
    return response.content


async def format_data(docs):
    formatted_content = []
    for doc in docs:
        # Extract content and metadata from LangChain Document objects
        content = doc.page_content
        metadata = doc.metadata.get("original_filename") if doc.metadata else None

        # Format the document for context
        doc_info = f"Content: {content}"
        if metadata:
            doc_info += f"\nOriginal Filename: {metadata}"

        formatted_content.append(doc_info)

    return "\n\n---\n\n".join(formatted_content)

@mcp.tool()
async def rag_knowledge_base(user_query:str):
    """
    Tool to retrieve the spicif knowledge based on the query.this tool return the exact content related to the query. if you are looking for the answer related to the query, this tool is for you.
    Args:
        Takes the user refined query as an argument.
    Returns:
        The exact content related to the query, or an error if not found.
    """
    try:
        # Get user context from token
        header = get_http_headers(include_all=True)
        tenant_id = header.get("tenant_id")
        user_id = header.get("user_id")
        if not user_id:
            return {
                "error": "Missing user_id in token",
                "status": "error",
            }
        if not tenant_id:
            return {
                "error": "Missing tenant_id in token",
                "status": "error",
            }
        logger.info(f"Query: {user_query}")
        logger.info(f"Knowledge base request from user: {user_id}, tenant: {tenant_id}")
        logger.info(f"Query: {user_query}")
        db_generator = get_db()
        db = await db_generator.__anext__()
        try:
            # Find tenant by tenant_id (custom identifier)
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.tenant_id == tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()
            if not tenant:
                return {"error": f"Tenant '{tenant_id}' not found", "status": "error"}

            # Get the knowledge base entry to retrieve collection name
            actual_tenant_id = str(tenant.id)
            kb_query = (
                select(KnowledgeBase)
                .where(KnowledgeBase.tenant_id == actual_tenant_id)
            )
            kb_result = await db.execute(kb_query)
            kb_entry = kb_result.scalars().first()

            if not kb_entry or not kb_entry.pgvector_collection_name:
                return {"error": "No knowledge base or collection name found for this tenant", "status": "error"}

            collection_name = kb_entry.pgvector_collection_name
            logger.info(f"Using collection: {collection_name} for tenant: {tenant_id}, user: {user_id}")

            # Fetch vector data using collection name
            docs = await get_data(user_query, collection_name, user_id)
            cleaned_data = await format_data(docs)
            if not docs:
                return {"error": "I do not have enough information to answer that question.", "status": "error"}

            response = await get_answer(user_query, cleaned_data)
            return {
                "status": "success",
                "data": response
            }

        except Exception as e:
            logger.error(f"Error fetching knowledge base: {e}")
            return {"error": f"Error fetching knowledge base: {e}", "status": "error"}
    except Exception as e:
        logger.error(f"Error fetching knowledge base: {e}")
        return {"error": f"Error fetching knowledge base: {e}", "status": "error"}