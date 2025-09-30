from sqlalchemy import select
from summarization.database.connection import get_db
from summarization.database.models import Tenant, KnowledgeBase
from summarization.prompts import system_prompt_for_summarization
from summarization.config.settings import settings
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
import json
import logging

logger = logging.getLogger(__name__)

mcp = FastMCP("Data Summarization")

# Initialize LLMs
openai_llm = ChatOpenAI(
    model=settings.openai_summarization_model,
    temperature=settings.openai_temperature,
    api_key=settings.openai_api_key
)

gemini_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

def get_llm(model_provider: str):
    """Get the appropriate LLM based on model provider"""
    if model_provider and model_provider.lower() == "gemini":
        return gemini_llm
    return openai_llm  # Default to OpenAI

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
        model_provider = header.get("model_provider", "openai")  # Default to openai if not provided

        if not tenant_id:
            return {
                "error": "Missing tenant_id in token",
                "status": "error",
            }

        logger.info(f"Summarization request from user: {user_id}, tenant: {tenant_id}, model: {model_provider}")

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

            # Convert knowledge_entries to LangChain Document objects
            all_documents = []
            for entry in knowledge_entries:
                try:
                    # Parse the stored content as JSON (should be list of Document dicts)
                    if entry.content.startswith("[") or entry.content.startswith("{"):
                        raw_data = json.loads(entry.content)
                        # Convert to LangChain Document objects
                        documents = [Document(**doc) for doc in raw_data] if isinstance(raw_data, list) else [Document(**raw_data)]
                        all_documents.extend(documents)
                    else:
                        # Handle plain text content
                        all_documents.append(Document(page_content=entry.content, metadata={"source": "raw_text"}))
                except (json.JSONDecodeError, TypeError) as e:
                    # Fallback for malformed content
                    all_documents.append(Document(page_content=str(entry.content), metadata={"source": "fallback", "error": str(e)}))

            # Format documents for summarization
            formatted_content = []
            for doc in all_documents:
                content = doc.page_content
                metadata = doc.metadata.get("original_filename") if doc.metadata else None

                doc_info = f"Content: {content}"
                if metadata:
                    doc_info += f"\nOriginal Filename: {metadata}"

                formatted_content.append(doc_info)

            # Join all content for summarization
            text_to_summarize = "\n\n---\n\n".join(formatted_content)

            if len(text_to_summarize.strip()) < 10:
                return {
                    "error": "Insufficient content for summarization",
                    "status": "error",
                }

            # Generate summary using appropriate LLM
            prompt = ChatPromptTemplate([("system", system_prompt_for_summarization), ("user", "Text To summarize: ```{text}```")])
            llm = get_llm(model_provider)

            chain = prompt | llm
            response = await chain.ainvoke({"text": text_to_summarize})

            return {
                "summary": response.content,
                "status": "success"
            }

        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Error during summarization: {str(e)}")
        return {
            "error": f"Failed to generate summary: {str(e)}",
            "status": "error",
        }