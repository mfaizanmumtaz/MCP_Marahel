from fastapi import FastAPI
import asyncio
import sys
from superviser_agent import chatbot_agent
from ingestion_api.api.router import ingestion_api

# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


app = FastAPI(
    title="Supervisor Agent API",
    description="API for knowledge base queries, translation, and summarization",
)

# Ingestion API
app.include_router(ingestion_api, prefix="/api")
app.include_router(chatbot_agent, prefix="/api")


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
