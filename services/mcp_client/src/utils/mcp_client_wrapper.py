"""
Robust MCP Client Wrapper with retry logic, health checks, and graceful degradation.
Handles connection failures and provides fallback responses when MCP servers are unavailable.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)


class MCPConnectionError(Exception):
    """Custom exception for MCP connection issues"""
    pass


class RobustMCPClient:
    """
    A wrapper around MultiServerMCPClient that provides:
    - Retry logic with exponential backoff
    - Health checks
    - Graceful degradation
    - Connection pooling
    - Fallback responses
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        timeout: float = 30.0,
        health_check_interval: float = 60.0
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.health_check_interval = health_check_interval

        self._client: Optional[MultiServerMCPClient] = None
        self._last_health_check = 0
        self._is_healthy = False
        self._connection_attempts = 0
        self._last_connection_error: Optional[str] = None

    async def _create_client(self, user_id: str, tenant_id: str, model_provider: str = None) -> MultiServerMCPClient:
        """Create a new MCP client instance"""
        mcp_server_url = settings.MCP_SERVER_URL
        headers = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "Connection": "keep-alive",
            "Keep-Alive": "timeout=30, max=100"
        }

        # Add model_provider to headers if provided
        if model_provider:
            headers["model_provider"] = model_provider

        client_config = {
            "Services": {
                "url": mcp_server_url,
                "transport": "streamable_http",
                "headers": headers,
                "timeout": self.timeout
            }
        }
        return MultiServerMCPClient(client_config)

    async def _test_connection(self) -> bool:
        """Test MCP connection by attempting to create a client"""
        try:
            # Skip frequent connection tests
            current_time = time.time()
            if current_time - self._last_health_check < self.health_check_interval:
                return self._is_healthy

            # Try to create a test client and get tools
            test_client = await self._create_client("test", "test")
            # Just try to get tools to test connection
            await test_client.get_tools()
            self._is_healthy = True

        except Exception as e:
            logger.warning(f"Connection test failed: {str(e)}")
            self._is_healthy = False

        self._last_health_check = current_time
        return self._is_healthy

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with retry logic and exponential backoff"""
        last_exception = None
        delay = self.retry_delay

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                self._connection_attempts += 1
                self._last_connection_error = str(e)

                logger.warning(
                    f"MCP operation failed (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}"
                )

                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= self.backoff_factor

        # All retries failed
        raise MCPConnectionError(f"Failed after {self.max_retries + 1} attempts: {str(last_exception)}")

    async def get_tools_with_fallback(self, user_id: str, tenant_id: str, model_provider: str = None) -> List[BaseTool]:
        """Get tools from MCP server with fallback to empty list"""
        try:
            # Try to get tools with retry logic
            async def _get_tools():
                if not self._client:
                    self._client = await self._create_client(user_id, tenant_id, model_provider)
                return await self._client.get_tools()

            tools = await self._retry_with_backoff(_get_tools)
            logger.info(f"Successfully retrieved {len(tools)} tools from MCP server")
            self._is_healthy = True  # Mark as healthy on successful operation
            return tools

        except MCPConnectionError as e:
            logger.error(f"MCP connection failed: {str(e)}")
            self._is_healthy = False
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting tools: {str(e)}")
            self._is_healthy = False
            return []

    async def invoke_tool_with_fallback(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: str,
        tenant_id: str,
        model_provider: str = None
    ) -> Dict[str, Any]:
        """Invoke tool with fallback response"""
        try:
            async def _invoke_tool():
                if not self._client:
                    self._client = await self._create_client(user_id, tenant_id, model_provider)

                # Get tools and find the requested one
                tools = await self._client.get_tools()
                target_tool = None

                for tool in tools:
                    if hasattr(tool, 'name') and tool.name == tool_name:
                        target_tool = tool
                        break

                if not target_tool:
                    raise ValueError(f"Tool '{tool_name}' not found")

                # Invoke the tool
                return await target_tool.ainvoke(arguments)

            result = await self._retry_with_backoff(_invoke_tool)
            self._is_healthy = True  # Mark as healthy on successful operation
            return {"status": "success", "result": result}

        except MCPConnectionError as e:
            logger.error(f"MCP tool invocation failed: {str(e)}")
            self._is_healthy = False
            return self._get_fallback_response(tool_name, str(e))
        except Exception as e:
            logger.error(f"Unexpected error invoking tool: {str(e)}")
            self._is_healthy = False
            return self._get_fallback_response(tool_name, str(e))

    def _get_fallback_response(self, tool_name: str, error_message: str) -> Dict[str, Any]:
        """Generate appropriate fallback response based on tool type"""
        fallback_responses = {
            "cag_knowledge_base": {
                "status": "fallback",
                "message": "I apologize, but I'm currently unable to access the knowledge base. The service might be temporarily unavailable. Please try again in a moment, or contact support if the issue persists.",
                "error": error_message
            },
            "rag_knowledge_base": {
                "status": "fallback",
                "data": "I'm sorry, but I cannot search through your documents at the moment due to a service interruption. Please try your query again shortly.",
                "error": error_message
            },
            "get_summarization": {
                "status": "fallback",
                "summary": "I apologize, but the summarization service is currently unavailable. Please try again later or contact your administrator.",
                "error": error_message
            },
            "get_translation": {
                "status": "fallback",
                "translation": "Translation service is temporarily unavailable. Please try again in a few moments.",
                "target_language": "unknown",
                "error": error_message
            }
        }

        return fallback_responses.get(tool_name, {
            "status": "fallback",
            "message": f"The requested service '{tool_name}' is temporarily unavailable. Please try again later.",
            "error": error_message
        })

    async def close(self):
        """Clean up client connections"""
        if self._client:
            try:
                # If the client has a close method, call it
                if hasattr(self._client, 'close'):
                    await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing MCP client: {str(e)}")
            finally:
                self._client = None

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics for monitoring"""
        return {
            "is_healthy": self._is_healthy,
            "connection_attempts": self._connection_attempts,
            "last_health_check": self._last_health_check,
            "last_connection_error": self._last_connection_error,
            "client_connected": self._client is not None
        }


# Global instance with settings configuration
robust_mcp_client = RobustMCPClient(
    max_retries=settings.MCP_MAX_RETRIES,
    retry_delay=settings.MCP_RETRY_DELAY,
    backoff_factor=settings.MCP_BACKOFF_FACTOR,
    timeout=settings.MCP_TIMEOUT,
    health_check_interval=settings.MCP_HEALTH_CHECK_INTERVAL
)


async def get_robust_mcp_client() -> RobustMCPClient:
    """Get the global robust MCP client instance"""
    return robust_mcp_client