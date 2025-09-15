from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from rag.database.pg_vector import get_data as get_vector_data
from dotenv import load_dotenv, find_dotenv
import json
import logging
from sqlalchemy import select
from rag.database.connection import get_db
from rag.database.models import Tenant, KnowledgeBase
from rag.utils.formate_documents import extract_usefull_info

logger = logging.getLogger(__name__)

# app = FastAPI()

load_dotenv(find_dotenv())

# Initialize FastMCP without auth parameter since we handle JWT manually

mcp = FastMCP("RAG KnowledgeBase")

@mcp.tool()
async def rag_knowledge_base(query:str):
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
        logger.info(f"Query: {query}")
        logger.info(f"Knowledge base request from user: {user_id}, tenant: {tenant_id}")
        logger.info(f"Query: {query}")
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
            kb_entry = kb_result.scalar_one_or_none()

            if not kb_entry or not kb_entry.pgvector_collection_name:
                return {"error": "No knowledge base or collection name found for this tenant", "status": "error"}

            collection_name = kb_entry.pgvector_collection_name
            logger.info(f"Using collection: {collection_name} for tenant: {tenant_id}, user: {user_id}")

            # Fetch vector data using collection name
            vector_results = await get_vector_data(query, collection_name, user_id)
            data = await extract_usefull_info(vector_results)

            return {
                "status": "success",
                "data":data
            }

        except Exception as e:
            logger.error(f"Error fetching knowledge base: {e}")
            return {"error": f"Error fetching knowledge base: {e}", "status": "error"}
    except Exception as e:
        logger.error(f"Error fetching knowledge base: {e}")
        return {"error": f"Error fetching knowledge base: {e}", "status": "error"}