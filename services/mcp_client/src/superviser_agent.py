from fastapi import APIRouter, HTTPException
from langchain_openai import ChatOpenAI
import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent
from langchain_core.messages.utils import trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from fastapi.responses import JSONResponse
from schema.schmas import QueryRequest
from langchain_mcp_adapters.client import MultiServerMCPClient
from prompts.prompts import get_prompt_for_permissions
from urllib.parse import quote_plus
from permissions.permission_manager import permission_manager
from prompts.few_short_prompts import examples
from config.settings import settings

# Create router instead of FastAPI app
chatbot_agent = APIRouter(tags=["Chat Agent"])


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
async def _chatbot_agent(request: QueryRequest):
    """Create an agent graph with the specified user_id and chatbot_id"""
    query = request.query
    user_id = request.user_id
    tenant_id = request.tenant_id
    session_id = request.session_id


    try:
        try:
            mcp_server_url = settings.MCP_SERVER_URL
            translation_summarization_client = MultiServerMCPClient(
                {
                    "Services": {
                        "url": mcp_server_url,
                        "transport": "streamable_http",
                        "headers": {"user_id": user_id, "tenant_id": tenant_id},
                    }
                }
            )

            # Get tools from both clients
            all_tools = await translation_summarization_client.get_tools()

            # Get tenant permissions for both tool filtering and prompt generation
            tenant_permissions = await permission_manager.get_tenant_permissions(tenant_id)

            # Filter tools based on tenant permissions
            tools = await permission_manager.filter_tools_by_permissions(all_tools, tenant_id)

            # Generate dynamic prompt based on available tools
            dynamic_prompt = get_prompt_for_permissions(tenant_permissions)

            # Check if no tools are available after filtering
            if not tools:
                return JSONResponse(
                    content={
                        "response": "I apologize, but you don't have access to any tools at the moment. Please contact your administrator to enable tool access for your account."
                    },
                    status_code=200
                )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Error fetching tools please make sure your mcp server is runing.",
            )

        llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.5)

        # config = {"configurable": {"thread_id": f"{tenant_id}"}}

        DB_URI = settings.PGVECTOR_CONNECTION_LEGACY

        if not DB_URI:
            raise ValueError("pgvector_connection environment variable is required")

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
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")





