# MCP_Marahel

This project implements a comprehensive Multi-Modal Content Processing (MCP) system with RAG capabilities, translation services, and summarization features.

## Project Structure

```
MCP_Marahel/
├── src/                          # Core application source code
│   ├── main.py                   # Main FastAPI application
│   ├── superviser_agent.py       # Supervisor agent implementation
│   ├── run_mcp_servers.py        # MCP servers runner
│   ├── rag_cag_agent/           # RAG and CAG agent modules
│   ├── ingestion_api/           # Data ingestion API
│   ├── translation/             # Translation services
│   ├── summarization/           # Text summarization
│   ├── prompts/                 # System prompts
│   └── schema/                  # Data schemas
├── apps/                        # Streamlit applications
│   ├── streamlit_comprehensive.py  # Main comprehensive app
│   └── streamlit_mcp_agent.py      # MCP agent specific app
├── scripts/                     # Runner and utility scripts
│   ├── run_api.py              # Run FastAPI server
│   ├── run_mcp_servers.py      # Run MCP servers
│   ├── run_streamlit_comprehensive.py  # Run comprehensive app
│   └── run_streamlit_mcp.py    # Run MCP agent app
├── qa_testing/                 # Quality assurance and testing
├── log/                        # Application logs
├── pyproject.toml             # Project configuration
├── uv.lock                    # Dependency lock file
└── README.md                  # This file
```

## Quick Start

### Option 1: Using the Unified Runner (Recommended)

```bash
# Start MCP servers (required first)
python run.py mcp

# Start FastAPI server (in a new terminal)
python run.py api

# Start Streamlit applications (in new terminals)
python run.py app      # Comprehensive app (port 8501)
python run.py agent    # MCP agent app (port 8502)
```

### Option 2: Using Individual Scripts

**1. Run MCP Servers:**
```bash
python scripts/run_mcp_servers.py
```

**2. Run FastAPI Server:**
```bash
python scripts/run_api.py
```

**3. Run Streamlit Applications:**
```bash
# Comprehensive App (port 8501)
python scripts/run_streamlit_comprehensive.py

# MCP Agent App (port 8502)
python scripts/run_streamlit_mcp.py
```

### Access Points

- **FastAPI Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Comprehensive Streamlit App**: http://localhost:8501
- **MCP Agent Streamlit App**: http://localhost:8502
- **MCP Servers**:
  - Translation & Summarization: http://127.0.0.1:8001/mcp
  - Knowledge Base: http://127.0.0.1:8003

## Development Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   # or if using uv
   uv sync
   ```

2. **Environment Configuration:**
   - Copy `.env.example` to `.env`
   - Configure your database connections and API keys

3. **Database Setup:**
   - Ensure PostgreSQL is running
   - Configure connection strings in `.env`

## Usage Examples

### Using the Unified Runner
```bash
# Show help
python run.py help

# Start all services (run each in separate terminals)
python run.py mcp      # Terminal 1: MCP servers
python run.py api      # Terminal 2: FastAPI server
python run.py app      # Terminal 3: Streamlit app
```

## Project Components

### Core Services

- **FastAPI Server** (`src/main.py`): Main API server handling requests
- **Supervisor Agent** (`src/superviser_agent.py`): Orchestrates different AI services
- **MCP Servers** (`src/run_mcp_servers.py`): Unified MCP server runner

### AI Services


- **RAG/CAG Agent** (`src/rag_cag_agent/`): Knowledge base search and retrieval
- **Translation Service** (`src/translation/`): Multi-language translation
- **Summarization Service** (`src/summarization/`): Text summarization
- **Ingestion API** (`src/ingestion_api/`): Document ingestion and processing

### User Interfaces

- **Comprehensive App** (`apps/streamlit_comprehensive.py`): Full-featured interface
- **MCP Agent App** (`apps/streamlit_mcp_agent.py`): Specialized MCP interface

### Utilities

- **Runner Scripts** (`scripts/`): Individual service runners
- **QA Testing** (`qa_testing/`): Testing utilities and queries

## Architecture

The system follows a microservices architecture:

1. **MCP Servers**: Handle specific AI tasks (translation, summarization, knowledge base)
2. **FastAPI Server**: Provides REST API endpoints and orchestrates services
3. **Streamlit Apps**: Provide user-friendly web interfaces
4. **Database Layer**: PostgreSQL for data persistence and vector storage

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Ensure ports 8000, 8001, 8003, 8501, 8502 are available
2. **Database Connection**: Check PostgreSQL is running and connection strings are correct
3. **Environment Variables**: Ensure all required variables are set in `.env`
4. **Dependencies**: Run `pip install -r requirements.txt` or `uv sync`

### Logs

- Application logs are stored in the `log/` directory
- Check individual terminal outputs for real-time debugging

## Contributing

1. Follow the established project structure
2. Add new services to `src/` directory
3. Create corresponding runner scripts in `scripts/`
4. Update documentation and tests
5. Use the unified runner for testing
