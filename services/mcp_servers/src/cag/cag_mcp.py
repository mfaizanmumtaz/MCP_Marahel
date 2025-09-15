from sqlalchemy import select
from cag.database.connection import get_db
from cag.database.models import KnowledgeBase, Tenant
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from dotenv import load_dotenv, find_dotenv
import json
import logging

logger = logging.getLogger(__name__)

# app = FastAPI()

load_dotenv(find_dotenv())

# Initialize FastMCP without auth parameter since we handle JWT manually

mcp = FastMCP("Raw KnowledgeBase")


@mcp.tool()
async def get_knowledge_base():
    """
    Tool to retrieve raw knowledge base data.
    This tool fetches the stored knowledge base content from the database,
    allowing you to access relevant information for further processing,
    search, or analysis and answering user queries.

    Returns:
        The raw knowledge base data, or an error if not found.
    """

    try:
        # Get user context from token
        header = get_http_headers(include_all=True)
        # print(header)
        # header = {"tenant_id": "marahel_abc1", "user_id": "string"}  # For testing without auth
        tenant_id = header.get("tenant_id")
        user_id = header.get("user_id")

        if not tenant_id:
            return {
                "error": "Missing tenant_id in token",
                "status": "error",
            }

        print(f"Knowledge base request from user: {user_id}, tenant: {tenant_id}")

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

            # Use the actual UUID for querying knowledge base
            actual_tenant_id = str(tenant.id)

            # Query knowledge base entries
            if user_id:
                # If user_id is provided, fetch ONLY user-specific data
                query = (
                    select(KnowledgeBase)
                    .where(KnowledgeBase.user_id == user_id)
                    .order_by(KnowledgeBase.created_at.desc())
                )
            else:
                # If user_id is not provided, fetch ONLY tenant-level data (exclude user-specific data)
                query = (
                    select(KnowledgeBase)
                    .where(
                        KnowledgeBase.tenant_id == actual_tenant_id,
                        KnowledgeBase.user_id.is_(None),
                    )
                    .order_by(KnowledgeBase.created_at.desc())
                )

            result = await db.execute(query)
            knowledge_entries = result.scalars().all()

            return {
                "total_entries": len(knowledge_entries),
                "entries": [
                    {
                        "content": json.loads(entry.content)
                        if entry.content.startswith("[")
                        or entry.content.startswith("{")
                        else entry.content,
                    }
                    for entry in knowledge_entries
                ],
            }

        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Error retrieving content: {str(e)}")
        return {"error": f"Failed to retrieve content: {str(e)}", "status": "error"}


if __name__ == "__main__":
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8003)
    if __name__ == "__main__":
        mcp.run(transport="http")
