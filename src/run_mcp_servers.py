from rag_cag_agent.cag_rag_mcp import mcp as knowledge_base_mcp 
from translation.translation import mcp as translation_mcp
from summarization.summarization import mcp as summarization_mcp

from fastmcp import FastMCP

# Create main server
mcp = FastMCP(
    name="UnifiedMCPServer",
    instructions="""
    This unified server provides three main capabilities:
    1. Knowledge Base operations - search and retrieve information from stored documents
    2. Translation services - translate text between different languages
    3. Text summarization - create concise summaries of long text content
    """
)

# Mount the individual servers with appropriate prefixes
mcp.mount(knowledge_base_mcp)
mcp.mount(translation_mcp) 
mcp.mount(summarization_mcp)

if __name__ == "__main__":
    # mcp.run(transport="streamable-http")
    mcp.run(transport="http", host="127.0.0.1", port=8001, path="/mcp")

