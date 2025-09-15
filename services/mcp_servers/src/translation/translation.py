from sqlalchemy import select
from translation.database.connection import get_db
from translation.database.models import Tenant, KnowledgeBase
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

mcp = FastMCP("Data Translation")


system_prompt = """You are a professional translator with expertise in {target_language} language.
You will receive a block of text and your task is to translate it accurately to the {target_language} language while preserving the original meaning, tone, and context.
Your translation should be natural, fluent, and culturally appropriate for the target language."""

@mcp.tool()
async def get_translation(target_language: str) -> dict:
    """Fetch knowledge base data and generate comprehensive translation.

    Translate the whole content of the knowledge base to the specified target language.

    Args:
        target_language (str): The target language to translate to (e.g., 'Spanish', 'French', 'Arabic', 'English').

    Returns:
        Response containing the translated content or error information.
    """
    try:
        # Get user context from token
        header = get_http_headers(include_all=True)
        tenant_id = header.get("tenant_id")
        user_id = header.get("user_id")

        # Validate input
        if not target_language:
            return {
                "error": "Target language must be specified",
                "status": "error",
            }

        if not tenant_id:
            return {
                "error": "Missing tenant_id in token",
                "status": "error",
            }

        logger.info(f"Translation request from user: {user_id}, tenant: {tenant_id}, target_language: {target_language}")

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
                    "error": "No knowledge base data found for translation",
                    "status": "error",
                }

            # Extract and combine all content for translation
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

            # Join all content for translation
            text_to_translate = "\n\n".join(combined_content)

            if len(text_to_translate.strip()) < 10:
                return {
                    "error": "Insufficient content for translation",
                    "status": "error",
                }

            # Initialize OpenAI client and generate translation
            prompt = ChatPromptTemplate([
                ("system", system_prompt),
                ("user", "Text to translate: ```{text}``` \nTarget language: {target_language}")            ])
            translation_pipeline = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            chain = prompt | translation_pipeline
            response = await chain.ainvoke({"text": text_to_translate,"target_language": target_language})

            return {
                "translation": response.content,
                "target_language": target_language,
                "status": "success"
            }

        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Error during translation: {str(e)}")
        return {
            "error": f"Failed to generate translation: {str(e)}",
            "status": "error",
        }


if __name__ == "__main__":
    mcp.run(transport="http")
