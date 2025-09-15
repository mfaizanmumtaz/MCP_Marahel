from sqlalchemy import select
from summarization.database.connection import get_db
from summarization.database.models import Tenant, KnowledgeBase
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os
import json
import logging
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())

mcp = FastMCP("Data Summarization")


system_prompt = """You are a helpful assistant designed to summarize text concisely and accurately.
You will receive a block of text and your task is to generate a brief summary that captures the main points and essential information.
Your summary should be clear, coherent, and easy to understand, avoiding unnecessary details or jargon."""

@mcp.tool()
async def get_summarization() -> dict:
    """Fetch knowledge base data and generate comprehensive summary.

    Retrieves all knowledge base entries for the authenticated tenant/user
    and generates a comprehensive summary of the content.

    Returns:
        Response containing the summarized content or error information.
    """
    try:
        # Get user context from token
        header = get_http_headers(include_all=True)
        tenant_id = header.get("tenant_id")
        user_id = header.get("user_id")

        if not tenant_id:
            return {
                "error": "Missing tenant_id in token",
                "status": "error",
            }

        logger.info(f"Summarization request from user: {user_id}, tenant: {tenant_id}")

        # Verify tenant exists
        db_generator = get_db()
        db = await db_generator.__anext__()
        try:
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.tenant_id == tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()
            if not tenant:
                return {
                    "error": f"Tenant '{tenant_id}' not found",
                    "status": "error",
                }

            # Use the actual UUID for querying knowledge base
            actual_tenant_id = str(tenant.id)

            # Query knowledge base entries like in cag_mcp.py
            if user_id:
                # If user_id is provided, fetch ONLY user-specific data
                query = (
                    select(KnowledgeBase)
                    .where(KnowledgeBase.user_id == user_id)
                    .order_by(KnowledgeBase.created_at.desc())
                )
            else:
                # If user_id is not provided, fetch ONLY tenant-level data
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

            if not knowledge_entries:
                return {
                    "error": "No knowledge base data found for summarization",
                    "status": "error",
                }

            # Extract and combine all content for summarization
            combined_content = []
            for entry in knowledge_entries:
                content = (
                    json.loads(entry.content)
                    if entry.content.startswith("[")
                    or entry.content.startswith("{")
                    else entry.content
                )

                if isinstance(content, list):
                    combined_content.extend([str(item) for item in content])
                elif isinstance(content, dict):
                    combined_content.append(str(content))
                else:
                    combined_content.append(str(content))

            # Join all content for summarization
            text_to_summarize = "\n\n".join(combined_content)

            if len(text_to_summarize.strip()) < 10:
                return {
                    "error": "Insufficient content for summarization",
                    "status": "error",
                }

            # Initialize OpenAI client and generate summary
            prompt = ChatPromptTemplate([("system", system_prompt), ("user", "Text To summarize: ```{text}```")])
            summarization_pipeline = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            chain = prompt | summarization_pipeline
            response = await chain.ainvoke({"text": text_to_summarize})

            return {
                "summary": response.content,
                "status": "success"            }

        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Error during summarization: {str(e)}")
        return {
            "error": f"Failed to generate summary: {str(e)}",
            "status": "error",
        }


if __name__ == "__main__":
    mcp.run(transport="http")
