from translation.translation import mcp as translation_mcp
from summarization.summarization import mcp as summarization_mcp
from cag.cag_mcp import mcp as cag_mcp
from rag.rag_mcp import mcp as rag_mcp
from fastmcp import FastMCP

# Create main server
mcp = FastMCP(
    name="UnifiedMCPServer",
    instructions="""
    This unified server provides three main capabilities:
    1. Knowledge Base operations - search and retrieve information from stored documents
    2. Translation services - translate text between different languages
    3. Text summarization - create concise summaries of long text content
    """,
)

# Mount the individual servers with appropriate prefixes
mcp.mount(translation_mcp)
mcp.mount(summarization_mcp)
mcp.mount(cag_mcp)
mcp.mount(rag_mcp)

if __name__ == "__main__":
    # mcp.run(transport="streamable-http")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=9697, path="/mcp")
