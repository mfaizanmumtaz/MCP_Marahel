from fastapi import FastAPI
import asyncio
import sys
from superviser_agent import chatbot_agent
from ingestion_api.api.router import ingestion_api
# from rag_cag_agent.cag_rag_mcp import KnowledgeBase


# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# get_knowledge_base = KnowledgeBase(chatbot_id="1568de36-660b-11f0-9fe2-0242ac120002", user_id="asfddsafrsdf")


app = FastAPI(
    title="Supervisor Agent API",
    description="API for knowledge base queries, translation, and summarization",
)

# @app.post("/get_knowledge_base")
# async def get_knowledge_base_endpoint(query: str):
#     return await get_knowledge_base.get_knowledge_base(query_user=query)

# Ingestion API
app.include_router(ingestion_api, prefix="/api")
app.include_router(chatbot_agent, prefix="/api")
# app.include_router(get_knowledge_base, prefix="/api")


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
            "GET /docs": "API documentation",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
