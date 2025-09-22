from sqlalchemy import select
from cag.database.connection import get_db
from cag.database.models import KnowledgeBase, Tenant
from cag.prompts import system_prompt_for_cag_based_generation
from cag.config import settings
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("Raw KnowledgeBase")

# Initialize LLM with settings
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    api_key=settings.OPENAI_API_KEY,
    temperature=settings.OPENAI_TEMPERATURE
)

async def format_data(docs):
    formatted_content = []
    for doc in docs.get("documents", []):
        # Extract content and metadata from LangChain Document objects
        content = doc.page_content
        metadata = doc.metadata.get("original_filename") if doc.metadata else None

        # Format the document for context
        doc_info = f"Content: {content}"
        if metadata:
            doc_info += f"\nOriginal Filename: {metadata}"

        formatted_content.append(doc_info)

    return "\n\n---\n\n".join(formatted_content)


async def get_answer(query,docs):
    prompt = ChatPromptTemplate([
        ("system", system_prompt_for_cag_based_generation),
        ("user", "{query}")
    ])
    chain = prompt | llm
    response = await chain.ainvoke({"query": query, "context": docs})
    return response.content

@mcp.tool()
async def cag_knowledge_base(user_query:str):
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

            data = {
                "total_entries": len(knowledge_entries),
                "total_documents": len(all_documents),
                "documents": all_documents
            }
            formatted_data = await format_data(data)
            response = await get_answer(user_query,formatted_data)
            return response
        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Error retrieving content: {str(e)}")
        return {"error": f"Failed to retrieve content: {str(e)}", "status": "error"}

