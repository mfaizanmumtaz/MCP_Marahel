from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph.graph import MessagesState, START, StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage
from rag_cag_agent.cag_rag_mcp import KnowledgeBase
from langchain_openai import ChatOpenAI
from translation.translation import translate_text
from summarization.summarization import text_summarization
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv, find_dotenv
import asyncio
from typing import List, Dict, Any
import os

load_dotenv("../.env")

# PostgreSQL checkpointer import as per official documentation
# from langgraph.checkpoint.postgres import PostgresSaver

# Database configuration
# DB_URI = f"postgresql://{os.getenv('PG_USER_NAME')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_NAME')}"

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Global memory instance - shared across all requests
GLOBAL_MEMORY = None

async def get_memory():
    """Create and return AsyncSqliteSaver instance - only create once"""
    global GLOBAL_MEMORY
    if GLOBAL_MEMORY is None:
        conn = await aiosqlite.connect("agent_memory.db")  # Use persistent file instead of :memory:
        GLOBAL_MEMORY = AsyncSqliteSaver(conn)
    return GLOBAL_MEMORY

app = FastAPI(title="Supervisor Agent API", description="API for knowledge base queries, translation, and summarization")

class QueryRequest(BaseModel):
    user_id: str
    chatbot_id: str
    query: str

class MessageResponse(BaseModel):
    role: str
    content: str
    type: str

class QueryResponse(BaseModel):
    response_text: str

async def create_agent_graph(user_id: str, chatbot_id: str):
    """Create an agent graph with the specified user_id and chatbot_id"""
    
    # Create KnowledgeBase instance with provided parameters
    get_knowledge_base = KnowledgeBase(chatbot_id=chatbot_id, user_id=user_id)
    
    # Define tools
    tools = [translate_text, text_summarization, get_knowledge_base.get_knowledge_base]
    llm_with_tools = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)

    # System message
    sys_msg = SystemMessage(content="""You are a helpful AI assistant with access to several tools:

1. Knowledge Base (get_knowledge_base):
   - Use this tool for any user questions requiring factual information
   - When user ask any question and you thought you cannot answer,please use this tool to get the knowledge base answer.
   - Return knowledge base answers exactly as provided without modifications

2. Translation (translate_text):
   - Use this when users request text translation
   - Clearly indicate the source and target languages
   - Maintain the original meaning and context

3. Summarization (text_summarization):
   - Use this when users request text summarization
   - Preserve key points while condensing the content
   - Indicate when summarization is being performed

Guidelines:
- Always use the most appropriate tool for the task
- If a request is unclear, ask for clarification
- Maintain a professional and helpful tone
- Never make up information - rely on the tools provided

For each response:
1. Identify the appropriate tool
2. Apply the tool correctly
3. Present results clearly""")

    # Node
    async def assistant(state: MessagesState):
       return {"messages": [await llm_with_tools.ainvoke([sys_msg] + state["messages"])]}

    # Graph
    builder = StateGraph(MessagesState)

    # Define nodes: these do the work
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))

    # Define edges: these determine how the control flow moves
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant",
        tools_condition,
    )
    builder.add_edge("tools", "assistant")
    
    # Get the shared memory instance
    memory = await get_memory()
    
    # Compile and return the graph
    return builder.compile(checkpointer=memory)

@app.on_event("startup")
async def startup_event():
    """Initialize memory on startup"""
    await get_memory()

@app.post("/query")
async def process_query(request: QueryRequest, response_model=QueryResponse):
    """
    Process a query using the supervisor agent with specified user_id and chatbot_id
    """
    try:
        # Create agent graph with the provided user_id and chatbot_id
        react_graph = await create_agent_graph(request.user_id, request.chatbot_id)
        
        # Process the query with thread_id for conversation continuity
        messages = [HumanMessage(content=request.query)]
        config = {"configurable": {"thread_id": f"{request.user_id}_{request.chatbot_id}"}}
        result = await react_graph.ainvoke({"messages": messages}, config=config)
        
        return QueryResponse(response_text=result.get("messages")[-1].content)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Supervisor Agent API is running"}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to Supervisor Agent API",
        "endpoints": {
            "POST /query": "Process a query with user_id, chatbot_id, and query",
            "GET /health": "Health check",
            "GET /docs": "API documentation"
        }
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)