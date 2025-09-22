# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Docker Compose Development (Recommended)
```bash
make up              # Build and start all services with Docker Compose
make dev             # Run FastAPI server locally with hot reload (port 9696)
make down            # Stop and remove all containers
make logs            # Show logs from all services
make restart         # Restart all services
make shell-main      # Debug main API container
make shell-mcp       # Debug MCP servers container
```

### Legacy Python Development
```bash
# Start MCP servers (required first)
python run.py mcp

# Start FastAPI server (in new terminal)
python run.py api

# Start Streamlit applications (in new terminals)
python run.py app      # Comprehensive app (port 8501)
python run.py agent    # MCP agent app (port 8502)
```

### Package Management
```bash
uv sync              # Install dependencies (preferred)
pip install -r requirements.txt  # Alternative dependency installation
```

## Architecture Overview

### Multi-Service Architecture
This is a **Model Context Protocol (MCP) based system** with a microservices architecture:

#### MCP Client (`services/mcp_client/`)
- **Main API Server**: FastAPI application on port 8000 (dev: 9696)
- **Supervisor Agent**: LangGraph-powered orchestration agent
- **Ingestion API**: Document upload, processing, and vectorization
- **Permission Management**: Multi-tenant access control

#### MCP Servers (`services/mcp_servers/`)
- **RAG Server**: Retrieval Augmented Generation with vector search
- **CAG Server**: Content Augmented Generation with direct knowledge access
- **Translation Server**: Multi-language translation services
- **Summarization Server**: Text summarization capabilities
- **Unified Server**: Mounts all servers under single endpoint (port 9697)

### Database Architecture

#### PostgreSQL + pgvector
- **Multi-tenant isolation**: Separate tenant/user data with permissions
- **Vector storage**: pgvector extension for embeddings and similarity search
- **Async operations**: SQLAlchemy async with connection pooling (500 connections)

#### Connection Patterns
```python
# Async PostgreSQL (for application data)
DATABASE_URL = "postgresql+asyncpg://user:pass@host:port/db"

# Sync PostgreSQL (for pgvector - langchain-postgres requirement)
PGVECTOR_CONNECTION_LEGACY = "postgresql://user:pass@host:port/db?sslmode=disable"
```

### Document Processing Pipeline

#### Standard LangChain Document Structure
All document processing uses consistent `Document(page_content="data", metadata={"key":"value"})` format:

1. **Upload**: Multi-format support (PDF, Excel, CSV, images, audio)
2. **Extraction**: UniversalFileLoader handles format-specific parsing
3. **Standardization**: Convert all content to LangChain Document objects
4. **Chunking**: Text splitting (default: 800 chars, 300 overlap)
5. **Embedding**: OpenAI embeddings (text-embedding-3-small)
6. **Storage**:
   - PostgreSQL: JSON array of Document dictionaries
   - pgvector: Chunked documents with embeddings

#### Document Storage Format
```python
# PostgreSQL storage format
[
  {"page_content": "content", "metadata": {"source": "file.pdf", "page": 1}},
  {"page_content": "content", "metadata": {"source": "file.pdf", "page": 2}}
]
```

### MCP Server Pattern

Each MCP server follows this structure:
```python
from fastmcp import FastMCP

mcp = FastMCP("Service Name")

@mcp.tool()
async def service_function(parameters):
    # Service logic using LangChain Document format
    return response

# Server mounts at http://host:9697/mcp
```

### API Structure

#### Client Endpoints
- `/api/chat-bot`: Main conversational interface with supervisor agent
- `/api/content-extractor/`: Document upload and processing
- `/api/cag/`: CAG-specific document ingestion
- `/api/rag/`: RAG-specific document ingestion

#### Service Communication
- MCP servers: HTTP transport on port 9697 with `/mcp` path
- Header-based authentication: `X-Tenant-ID`, `X-User-ID`
- Async communication between client and servers

### Configuration Management

#### Environment Variables
Critical settings across all services:
```bash
# Database
PG_USER_NAME, PG_PASSWORD, PG_HOST, PG_PORT, PG_NAME

# AI Services
OPENAI_API_KEY, CLAUDE_API_KEY, OPENROUTER_API_KEY

# Document Processing
chunk_size=800, chunk_overlap=300

# MCP
MCP_SERVER_HOST=localhost, MCP_SERVER_PORT=8001
```

#### Service Ports
- FastAPI Client: 8000 (dev: 9696)
- MCP Servers: 9697
- Streamlit Comprehensive: 8501
- Streamlit Agent: 8502

### Multi-Tenancy & Permissions

#### Access Control Pattern
```python
# Tenant model with service-specific permissions
class Tenant:
    tenant_id: str           # Custom tenant identifier
    user_id: Optional[str]   # Optional user isolation
    summary_access: bool
    translation_access: bool
    rag_access: bool
    cag_access: bool
```

#### Data Isolation
- Tenant-level: Separate knowledge bases per tenant
- User-level: Optional user isolation within tenant
- Service-level: Permission-based access to each MCP service

### LangGraph Integration

#### Supervisor Agent Pattern
- **Message Trimming**: Token management with configurable limits
- **Tool Integration**: MCP adapters for seamless tool calling
- **State Management**: Persistent conversation history
- **Few-shot Prompting**: Examples stored in prompts directory

### Key Development Patterns

#### Async/Await Throughout
All database operations, MCP calls, and file processing use async patterns.

#### Error Handling
- Comprehensive logging across all services
- Graceful degradation when services unavailable
- User-friendly error messages in API responses

#### Document Processing
Always use the standardized LangChain Document format. Avoid complex nested structures.

#### pgvector Integration
Use synchronous connection string with `asyncio.run_in_executor()` to avoid AsyncEngine issues with langchain-postgres.

## Testing & Debugging

### Service Health Checks
```bash
make test-connection     # Test inter-service connectivity
make logs               # Monitor all service logs
```

### Access Points
- API Documentation: http://localhost:8000/docs (dev: http://localhost:9696/docs)
- Comprehensive UI: http://localhost:8501
- Agent UI: http://localhost:8502

### Common Issues
1. **Port conflicts**: Ensure ports 8000, 8501, 8502, 9697 are available
2. **pgvector errors**: Use `PGVECTOR_CONNECTION_LEGACY` for langchain-postgres
3. **Document format**: Always standardize to LangChain Document structure
4. **MCP connectivity**: Ensure MCP servers start before client services