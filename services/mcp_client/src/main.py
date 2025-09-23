import asyncio
import sys
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from config.settings import settings
from superviser_agent import chatbot_agent
from ingestion_api.api.router import ingestion_api
from utils.mcp_client_wrapper import get_robust_mcp_client

# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure LangSmith environment variables
os.environ["LANGSMITH_TRACING"] = settings.LANGSMITH_TRACING
os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle including MCP client cleanup"""
    logger.info("Starting MCP Client Application...")
    yield
    logger.info("Shutting down MCP Client Application...")

    # Clean up MCP client connections
    try:
        robust_client = await get_robust_mcp_client()
        await robust_client.close()
        logger.info("MCP client connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing MCP client connections: {str(e)}")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MCP Client API for knowledge base queries, translation, and summarization with robust error handling and graceful degradation",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(ingestion_api, prefix="/api")
app.include_router(chatbot_agent, prefix="/api")


@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    try:
        # Check MCP client stats without forcing a connection
        robust_client = await get_robust_mcp_client()
        mcp_stats = robust_client.get_connection_stats()

        health_status = {
            "status": "healthy",
            "message": f"{settings.PROJECT_NAME} is running",
            "mcp_connection_attempts": mcp_stats["connection_attempts"],
            "mcp_last_known_status": "healthy" if mcp_stats["is_healthy"] else "unknown"
        }

        return health_status

    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {
            "status": "healthy",
            "message": f"{settings.PROJECT_NAME} is running",
            "note": "Health check completed with warnings"
        }


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