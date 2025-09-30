from fastapi import APIRouter, HTTPException, Depends
from langchain_openai import ChatOpenAI
import os
import logging
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent
from langchain_core.messages.utils import trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from fastapi.responses import JSONResponse
from schema.schmas import QueryRequest
from prompts.prompts import get_prompt_for_permissions
from urllib.parse import quote_plus
from permissions.permission_manager import permission_manager
from prompts.few_short_prompts import examples
from config.settings import settings
from utils.mcp_client_wrapper import get_robust_mcp_client, MCPConnectionError
from ingestion_api.db.connection import get_db
from ingestion_api.db.models import ModelPreference
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_google_genai import ChatGoogleGenerativeAI

# Create router instead of FastAPI app
chatbot_agent = APIRouter(tags=["Chat Agent"])

# Configure logging
logger = logging.getLogger(__name__)


def pre_model_hook(state):
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=100000,
        start_on="human",
        end_on=("human", "tool"),
    )

    # Inject few-shot examples after system message
    if trimmed_messages and trimmed_messages[0].type == "system":
        # Keep system message first, then add few-shot examples, then rest of conversation
        final_messages = [trimmed_messages[0]] + examples + trimmed_messages[1:]
    else:
        # If no system message, just add few-shot examples at the beginning
        final_messages = examples + trimmed_messages

    return {"llm_input_messages": final_messages}


@chatbot_agent.post("/chat-bot")
async def _chatbot_agent(request: QueryRequest, db: AsyncSession = Depends(get_db)):
    """Create an agent graph with the specified user_id and chatbot_id"""
    query = request.query
    user_id = request.user_id
    tenant_id = request.tenant_id
    session_id = request.session_id


    try:
        # Get model preference for this tenant
        model_pref_result = await db.execute(
            select(ModelPreference).where(ModelPreference.tenant_id == tenant_id)
        )
        model_pref = model_pref_result.scalar_one_or_none()
        model_provider = model_pref.model_provider if model_pref else "openai"  # Default to openai

        logger.info(f"Using model provider '{model_provider}' for tenant {tenant_id}")

        # Get robust MCP client instance
        robust_client = await get_robust_mcp_client()

        try:
            # Get tools using robust client with retry logic and fallback
            all_tools = await robust_client.get_tools_with_fallback(user_id, tenant_id, model_provider)

            # Get tenant permissions for both tool filtering and prompt generation
            tenant_permissions = await permission_manager.get_tenant_permissions(tenant_id)

            # Filter tools based on tenant permissions
            tools = await permission_manager.filter_tools_by_permissions(all_tools, tenant_id)

            # Generate dynamic prompt based on available tools
            dynamic_prompt = get_prompt_for_permissions(tenant_permissions)

            # Check if no tools are available after filtering
            if not tools:
                # Get connection stats for better error message
                stats = robust_client.get_connection_stats()

                if not stats["is_healthy"]:
                    logger.warning(f"MCP server unhealthy. Connection stats: {stats}")
                    return JSONResponse(
                        content={
                            "response": "I apologize, but the knowledge base services are temporarily unavailable. I can still help answer general questions, but I cannot access your specific documents or use specialized tools at the moment. Please try again in a few minutes or contact support if this issue persists."
                        },
                        status_code=200
                    )
                else:
                    return JSONResponse(
                        content={
                            "response": "I apologize, but you don't have access to any tools at the moment. Please contact your administrator to enable tool access for your account."
                        },
                        status_code=200
                    )

        except MCPConnectionError as e:
            logger.error(f"MCP connection error: {str(e)}")
            # Continue with empty tools list for graceful degradation
            tools = []
            tenant_permissions = await permission_manager.get_tenant_permissions(tenant_id)
            dynamic_prompt = get_prompt_for_permissions(tenant_permissions)

            # Add fallback message to prompt
            dynamic_prompt += "\n\nIMPORTANT: Knowledge base services are currently unavailable. Apologize to the user and offer to help with general questions while services are being restored."

        except Exception as e:
            logger.error(f"Unexpected error getting tools: {str(e)}")
            # Continue with empty tools list for graceful degradation
            tools = []
            tenant_permissions = await permission_manager.get_tenant_permissions(tenant_id)
            dynamic_prompt = get_prompt_for_permissions(tenant_permissions)

        # llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.5)
        if model_provider == "openai":
            llm = ChatOpenAI(
  api_key=settings.OPENAI_API_KEY,
  model=settings.OPENAI_MODEL,
  temperature=settings.OPENAI_TEMPERATURE)
        elif model_provider == "gemini":
            llm = ChatGoogleGenerativeAI(model=settings.GOOGLE_MODEL, google_api_key=settings.GOOGLE_API_KEY, temperature=settings.OPENAI_TEMPERATURE)

        # config = {"configurable": {"thread_id": f"{tenant_id}"}}

        DB_URI = settings.PGVECTOR_CONNECTION_LEGACY

        if not DB_URI:
            raise ValueError("pgvector_connection environment variable is required")

        # from pydantic import BaseModel
        # class MyCustomState(BaseModel):
        #     bit:bool = False

        async with AsyncPostgresSaver.from_conn_string(
            conn_string=DB_URI
        ) as checkpointer:
            # await checkpointer.setup()
            agent = create_react_agent(
                model=llm, 
                pre_model_hook=pre_model_hook,
                tools=tools,
                prompt=dynamic_prompt,
                checkpointer=checkpointer,
            )

            config = {"configurable": {"thread_id": f"{session_id}"}}

            response = await agent.ainvoke(
                {"messages": [{"role": "user", "content": query}]}, config
            )
            # print(response.get("messages"))
            ai_message = response.get("messages", [])[-1].content

            return JSONResponse(content={"response": f"{ai_message}"}, status_code=200)

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        # Attempt to clean up MCP client on error
        try:
            robust_client = await get_robust_mcp_client()
            await robust_client.close()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@chatbot_agent.get("/mcp-stats")
async def get_mcp_stats():
    """Get MCP connection statistics"""
    try:
        robust_client = await get_robust_mcp_client()
        stats = robust_client.get_connection_stats()

        return JSONResponse(content={
            "connection_attempts": stats["connection_attempts"],
            "last_known_status": "healthy" if stats["is_healthy"] else "unknown",
            "client_connected": stats["client_connected"],
            "last_error": stats["last_connection_error"] if stats["last_connection_error"] else None
        })

    except Exception as e:
        logger.error(f"Error getting MCP stats: {str(e)}")
        return JSONResponse(content={
            "error": "Could not retrieve MCP statistics",
            "details": str(e)
        }, status_code=500)





