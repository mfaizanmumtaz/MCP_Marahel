# MCP Client Resilience Features

This document describes the robust error handling and resilience features implemented in the MCP client to handle connection failures and server interruptions gracefully.

## Overview

The MCP (Model Context Protocol) client has been enhanced with comprehensive error handling, retry mechanisms, health checks, and graceful degradation capabilities to ensure uninterrupted service even when MCP servers experience issues.

## Features

### 1. Robust MCP Client Wrapper (`utils/mcp_client_wrapper.py`)

The `RobustMCPClient` class provides:

- **Retry Logic with Exponential Backoff**: Automatically retries failed connections with increasing delays
- **Health Checks**: Periodic monitoring of MCP server availability
- **Graceful Degradation**: Continues operation with limited functionality when servers are unavailable
- **Connection Pooling**: Efficient connection management with cleanup
- **Fallback Responses**: Provides meaningful responses when tools are unavailable

### 2. Configuration Options

Environment variables to control resilience behavior:

```bash
# Retry and timeout settings
MCP_MAX_RETRIES=3                    # Maximum retry attempts (default: 3)
MCP_RETRY_DELAY=1.0                  # Initial delay between retries in seconds (default: 1.0)
MCP_BACKOFF_FACTOR=2.0               # Exponential backoff multiplier (default: 2.0)
MCP_TIMEOUT=30.0                     # Connection timeout in seconds (default: 30.0)
MCP_HEALTH_CHECK_INTERVAL=60.0       # Health check interval in seconds (default: 60.0)
```

### 3. Enhanced Error Handling

#### Connection Failure Types Handled:
- Network timeouts (`httpx.ReadError`)
- Server unavailability (HTTP 5xx errors)
- Connection refused errors
- SSL/TLS errors
- Unexpected disconnections during streaming

#### Response Patterns:
1. **Immediate Retry**: For transient network issues
2. **Exponential Backoff**: For persistent connection problems
3. **Health Check Bypass**: Skip health checks for a period after failures
4. **Graceful Degradation**: Continue with limited functionality

### 4. Health Check Endpoints

#### Primary Health Check: `GET /health`
```json
{
  "status": "healthy|degraded|error",
  "message": "Service status description",
  "components": {
    "api": "healthy",
    "mcp_server": "healthy|degraded"
  },
  "mcp_details": {
    "server_healthy": true,
    "connection_attempts": 5,
    "client_connected": true
  }
}
```

#### MCP-Specific Health Check: `GET /api/health/mcp`
```json
{
  "mcp_server_healthy": true,
  "connection_attempts": 0,
  "last_health_check": 1643723400.0,
  "client_connected": true,
  "status": "healthy"
}
```

### 5. Fallback Behavior

When MCP servers are unavailable, the system provides appropriate fallback responses:

#### Knowledge Base Queries
```json
{
  "status": "fallback",
  "message": "I apologize, but I'm currently unable to access the knowledge base. The service might be temporarily unavailable. Please try again in a moment, or contact support if the issue persists."
}
```

#### Tool-Specific Fallbacks
- **CAG Knowledge Base**: General knowledge base unavailability message
- **RAG Search**: Document search service interruption notice
- **Summarization**: Summarization service unavailable message
- **Translation**: Translation service temporarily unavailable notice

### 6. Monitoring and Observability

#### Connection Statistics
The robust client tracks important metrics:
- Health check status and timestamps
- Total connection attempts
- Last connection error details
- Client connection state

#### Logging
Comprehensive logging at multiple levels:
- `INFO`: Successful operations and health status
- `WARNING`: Health check failures and retry attempts
- `ERROR`: Connection failures and fallback activations

## Implementation Details

### Retry Logic
```python
async def _retry_with_backoff(self, func, *args, **kwargs):
    """Execute function with retry logic and exponential backoff"""
    last_exception = None
    delay = self.retry_delay

    for attempt in range(self.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < self.max_retries:
                await asyncio.sleep(delay)
                delay *= self.backoff_factor

    raise MCPConnectionError(f"Failed after {self.max_retries + 1} attempts")
```

### Health Check Implementation
```python
async def _health_check(self) -> bool:
    """Check if MCP server is healthy"""
    try:
        # Skip frequent health checks
        current_time = time.time()
        if current_time - self._last_health_check < self.health_check_interval:
            return self._is_healthy

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                settings.MCP_SERVER_URL.replace('/mcp', '/health')
            )
            self._is_healthy = response.status_code == 200
    except Exception:
        self._is_healthy = False

    return self._is_healthy
```

### Graceful Degradation
When tools are unavailable due to MCP server issues, the system:

1. **Continues Operation**: The chatbot remains functional for general queries
2. **Informs Users**: Provides clear messaging about service limitations
3. **Maintains Context**: Preserves conversation history and user sessions
4. **Auto-Recovery**: Automatically reconnects when services become available

## Usage Examples

### Basic Usage in Supervisor Agent
```python
from utils.mcp_client_wrapper import get_robust_mcp_client

# Get robust client instance
robust_client = await get_robust_mcp_client()

# Get tools with automatic retry and fallback
tools = await robust_client.get_tools_with_fallback(user_id, tenant_id)

# Check connection health
stats = robust_client.get_connection_stats()
if not stats["is_healthy"]:
    # Handle degraded service
    pass
```

### Error Handling Pattern
```python
try:
    # Get tools using robust client
    all_tools = await robust_client.get_tools_with_fallback(user_id, tenant_id)

    # Continue with normal operation
    tools = await permission_manager.filter_tools_by_permissions(all_tools, tenant_id)

except MCPConnectionError as e:
    logger.error(f"MCP connection error: {str(e)}")
    # Graceful degradation - continue with empty tools
    tools = []
    # Add fallback message to prompt
    dynamic_prompt += "\\n\\nIMPORTANT: Knowledge base services are currently unavailable."
```

## Best Practices

### 1. Environment Configuration
- Set appropriate timeout values based on your network conditions
- Adjust retry counts based on expected server reliability
- Configure health check intervals to balance responsiveness and resource usage

### 2. Monitoring
- Monitor the `/health` endpoint for service status
- Set up alerts for prolonged MCP server unavailability
- Track connection attempt patterns to identify issues

### 3. User Experience
- Always provide clear messaging when services are degraded
- Maintain conversation continuity even during outages
- Implement automatic recovery without user intervention

### 4. Development and Testing
- Test failure scenarios during development
- Simulate network issues to verify fallback behavior
- Monitor logs for connection patterns and errors

## Troubleshooting

### Common Issues

#### High Connection Attempt Count
- Check MCP server health and availability
- Verify network connectivity between client and server
- Review timeout settings - may need adjustment for slow networks

#### Frequent Health Check Failures
- Verify MCP server `/health` endpoint is accessible
- Check for firewall or network routing issues
- Consider increasing health check interval if servers are stable

#### Fallback Responses Appearing Frequently
- Monitor MCP server logs for error patterns
- Check server resource utilization
- Verify server configuration and dependencies

### Log Analysis
Key log messages to monitor:
```
INFO: Successfully retrieved X tools from MCP server
WARNING: Health check failed: <error_details>
ERROR: MCP connection failed: <error_details>
WARNING: MCP server unhealthy. Connection stats: <stats>
```

## Future Enhancements

Potential improvements for even greater resilience:

1. **Circuit Breaker Pattern**: Temporarily stop attempting connections after repeated failures
2. **Multiple Server Support**: Failover to backup MCP servers
3. **Caching Layer**: Cache recent responses for offline operation
4. **Metrics Collection**: Detailed performance and reliability metrics
5. **Auto-scaling Integration**: Dynamic server scaling based on health metrics

## Summary


This implementation follows best practices for distributed systems and provides comprehensive monitoring and observability to help maintain service reliability.