from fastapi import APIRouter, HTTPException
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv, find_dotenv
import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent
from langchain_core.messages.utils import trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from fastapi.responses import JSONResponse
from schema.schmas import QueryRequest
from langchain_mcp_adapters.client import MultiServerMCPClient
from prompts.prompts import SYS_PROMPT_SUPERVISOR_AGENT

load_dotenv(find_dotenv())

# Create router instead of FastAPI app
chatbot_agent = APIRouter(tags=["Chat Bot Agent"])


def pre_model_hook(state):
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=50000,
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed_messages}


@chatbot_agent.post("/chat-bot")
async def _chatbot_agent(request: QueryRequest):
    """Create an agent graph with the specified user_id and chatbot_id"""
    query = request.query
    user_id = request.user_id
    chatbot_id = request.chatbot_id

    try:

        
        # Create MCP clients - authenticated only for KnowledgeBase
        try:
            translation_summarization_client = MultiServerMCPClient(
                {
                    "Translation": {
                        "url": "http://127.0.0.1:8001/mcp",
                        "transport": "streamable_http",
                        "headers": {
                            "user_id": chatbot_id,
                            "chatbot_id": chatbot_id
                        }
                    }}
            )
            

            # Get tools from both clients
            tools = await translation_summarization_client.get_tools()
        except Exception:
            raise HTTPException(status_code=500, detail="Error fetching tools please make sure your mcp server is runing.")
        
        # knowledge_base_tools = await knowledge_base_client.get_tools()

        llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.5)

        config = {"configurable": {"thread_id": f"{user_id}"}}

        # DB_URI = os.getenv("pgvector_connection")
        DB_URI = f"postgresql://{os.getenv('PG_USER_NAME')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_NAME')}?sslmode=require&connect_timeout=300"

        if not DB_URI:
            raise ValueError("pgvector_connection environment variable is required")
        async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
            # await checkpointer.setup()
            agent = create_react_agent(
                pre_model_hook=pre_model_hook,
                model=llm,
                tools=tools,
                prompt=SYS_PROMPT_SUPERVISOR_AGENT,
                checkpointer=checkpointer,
            )

            ai_message = ""
            first_message = True
            async for message in agent.astream(
                {"messages": [{"role": "user", "content": query}]}, config
            ):
                response = message.get("agent")
                if response:
                    content = response.get("messages", [])[0].content
                    if first_message:
                        ai_message += content
                        first_message = False
                    else:
                        ai_message += "\n\n" + content

            return JSONResponse(content={"response": ai_message}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")