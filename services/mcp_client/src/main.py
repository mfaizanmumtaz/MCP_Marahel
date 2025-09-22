import asyncio
import sys
import os
from fastapi import FastAPI

from config.settings import settings
from superviser_agent import chatbot_agent
from ingestion_api.api.router import ingestion_api

# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure LangSmith environment variables
os.environ["LANGSMITH_TRACING"] = settings.LANGSMITH_TRACING
os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MCP Client API for knowledge base queries, translation, and summarization",
    version="1.0.0",
)

# Include routers
app.include_router(ingestion_api, prefix="/api")
app.include_router(chatbot_agent, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": f"{settings.PROJECT_NAME} is running"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "GET /docs": "API documentation",
            "POST /api/...": "Various API endpoints for ingestion and chat",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level="info"
    )