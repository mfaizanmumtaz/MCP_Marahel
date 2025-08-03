import streamlit as st
import requests
import uuid
from datetime import datetime
from typing import Dict
import os
import sys
import asyncio
import json
from fastmcp import Client

# Add project source to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Streamlit page configuration
st.set_page_config(
    page_title="MCP Chatbot Interface", layout="wide", initial_sidebar_state="expanded"
)

# Global configuration
API_BASE_URL = "http://localhost:8000/api"

# MCP configuration base (will be updated with session state values)
MCP_BASE_CONFIG = {
    "mcp_servers": {
        "url": "http://127.0.0.1:8001/mcp",
        "headers": {}
    },
}


# Initialize session state
def initialize_session_state():
    """Initialize session state variables"""
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())

    if "chatbot_id" not in st.session_state:
        st.session_state.chatbot_id = str(uuid.uuid4())

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def clear_mcp_tools_cache():
    """Clear all MCP tools cache entries"""
    keys_to_remove = [key for key in st.session_state.keys() if key.startswith("mcp_tools_")]
    for key in keys_to_remove:
        del st.session_state[key]


def make_chat_request(query: str, user_id: str, chatbot_id: str) -> Dict:
    """Make request to chatbot API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat-bot",
            json={"query": query, "user_id": user_id, "chatbot_id": chatbot_id},
            timeout=60,
        )

        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code} - {response.text}",
            }

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection Error: {str(e)}"}


def upload_files_cag(files, chatbot_id: str, llm: str, session_id: str = None) -> Dict:
    """Upload files to CAG ingestion API"""
    try:
        files_data = []
        form_data = {"chatbot_id": chatbot_id, "llm": llm}

        if session_id:
            form_data["session_id"] = session_id

        for file in files:
            files_data.append(("files", (file.name, file.getvalue(), file.type)))

        response = requests.post(
            f"{API_BASE_URL}/cag-ingestion",
            data=form_data,
            files=files_data,
            timeout=120,
        )

        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "error": f"Upload Error: {response.status_code} - {response.text}",
            }

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection Error: {str(e)}"}


def upload_files_rag(
    files,
    chatbot_id: str,
    llm: str,
    chunk_size: int,
    chunk_overlap: int,
    embeddings_model: str,
    vectorstore_name: str,
) -> Dict:
    """Upload files to RAG ingestion API"""
    try:
        files_data = []
        form_data = {
            "chatbot_id": chatbot_id,
            "llm": llm,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "embeddings_model": embeddings_model,
            "vectorstore_name": vectorstore_name,
        }

        for file in files:
            files_data.append(("files", (file.name, file.getvalue(), file.type)))

        response = requests.post(
            f"{API_BASE_URL}/rag-ingestion",
            data=form_data,
            files=files_data,
            timeout=120,
        )

        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {
                "success": False,
                "error": f"Upload Error: {response.status_code} - {response.text}",
            }

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection Error: {str(e)}"}


def create_mcp_client(user_id: str, chatbot_id: str):
    """Create MCP client with dynamic user and chatbot IDs"""
    config = {
        "mcp_servers": {
            "url": "http://127.0.0.1:8001/mcp",
            "headers": {
                "user_id": user_id,
                "chatbot_id": chatbot_id
            }
        },
    }
    return Client(config)


async def get_available_tools(user_id: str, chatbot_id: str):
    """Get available MCP tools"""
    client = create_mcp_client(user_id, chatbot_id)
    async with client:
        tools = await client.list_tools()
        return tools


async def calling_tools(tool_name: str, tool_args: dict, user_id: str, chatbot_id: str):
    """Call an MCP tool with given arguments"""
    client = create_mcp_client(user_id, chatbot_id)
    async with client:
        res = await client.call_tool(tool_name, tool_args)
        return res


def parse_tool_result(result):
    """Parse CallToolResult into a readable dictionary format"""
    parsed_result = {
        "is_error": getattr(result, 'is_error', False),
        "data": getattr(result, 'data', None),
    }

    # Parse content if available
    if hasattr(result, 'content') and result.content:
        content_list = []
        for content_item in result.content:
            content_dict = {"type": getattr(content_item, 'type', 'unknown')}

            # Handle text content
            if hasattr(content_item, 'text'):
                content_dict["text"] = content_item.text

            # Handle other attributes
            if hasattr(content_item, 'annotations') and content_item.annotations:
                content_dict["annotations"] = content_item.annotations

            if hasattr(content_item, 'meta') and content_item.meta:
                content_dict["meta"] = content_item.meta

            content_list.append(content_dict)
        parsed_result["content"] = content_list

    # Parse structured_content if available
    if hasattr(result, 'structured_content') and result.structured_content:
        parsed_result["structured_content"] = result.structured_content

    # Try to extract the main result text from various sources
    main_text = None
    if parsed_result.get("data"):
        main_text = str(parsed_result["data"])
    elif parsed_result.get("structured_content") and isinstance(parsed_result["structured_content"], dict):
        if "result" in parsed_result["structured_content"]:
            main_text = str(parsed_result["structured_content"]["result"])
    elif parsed_result.get("content") and len(parsed_result["content"]) > 0:
        first_content = parsed_result["content"][0]
        if "text" in first_content:
            main_text = first_content["text"]

    parsed_result["main_result"] = main_text

    return parsed_result


def render_sidebar():
    """Render sidebar with ingestion APIs"""
    with st.sidebar:
        st.header("File Ingestion")

        # User and Chatbot ID management
        st.subheader("Configuration")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_input(
                "User ID",
                value=st.session_state.user_id,
                disabled=True,
                key="display_user_id",
            )
        with col2:
            if st.button("New User", help="Generate new User ID"):
                st.session_state.user_id = str(uuid.uuid4())
                clear_mcp_tools_cache()  # Clear MCP tools cache when ID changes
                st.rerun()

        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_input(
                "Chatbot ID",
                value=st.session_state.chatbot_id,
                disabled=True,
                key="display_chatbot_id",
            )
        with col2:
            if st.button("New Bot", help="Generate new Chatbot ID"):
                st.session_state.chatbot_id = str(uuid.uuid4())
                st.session_state.chat_history = []  # Clear history with new bot
                clear_mcp_tools_cache()  # Clear MCP tools cache when ID changes
                st.rerun()

        st.divider()

        # CAG Ingestion
        st.subheader("CAG Ingestion")
        with st.expander("Upload Files for CAG", expanded=False):
            cag_files = st.file_uploader(
                "Choose files for CAG",
                accept_multiple_files=True,
                type=["pdf", "docx", "doc", "csv", "xlsx"],
                key="cag_files",
            )

            cag_llm = st.selectbox("LLM Model", ["openai", "claude"], key="cag_llm")
            # cag_session_id = st.text_input("Session ID (Optional)", key="cag_session_id")

            if st.button("Upload to CAG", disabled=not cag_files):
                with st.spinner("Uploading files to CAG..."):
                    result = upload_files_cag(
                        cag_files, st.session_state.chatbot_id, cag_llm
                    )

                    if result["success"]:
                        st.success("Files uploaded successfully to CAG!")
                    else:
                        st.error(f"Upload failed: {result['error']}")

        # RAG Ingestion
        st.subheader("RAG Ingestion")
        with st.expander("Upload Files for RAG", expanded=False):
            rag_files = st.file_uploader(
                "Choose files for RAG",
                accept_multiple_files=True,
                type=["pdf", "docx", "doc", "txt"],
                key="rag_files",
            )

            col1, col2 = st.columns(2)
            with col1:
                rag_llm = st.selectbox("LLM Model", ["openai", "claude"], key="rag_llm")
                chunk_size = st.number_input(
                    "Chunk Size",
                    value=1000,
                    min_value=100,
                    max_value=2000,
                    key="chunk_size",
                )
            with col2:
                chunk_overlap = st.number_input(
                    "Chunk Overlap",
                    value=200,
                    min_value=0,
                    max_value=500,
                    key="chunk_overlap",
                )
                embeddings_model = st.selectbox(
                    "Embeddings Model", ["openai"], key="embeddings_model"
                )

            vectorstore_name = st.selectbox(
                "Vector Store", ["pgvector", "qdrant"], key="vectorstore_name"
            )

            if st.button("Upload to RAG", disabled=not rag_files):
                with st.spinner("Uploading files to RAG..."):
                    result = upload_files_rag(
                        rag_files,
                        st.session_state.chatbot_id,
                        rag_llm,
                        chunk_size,
                        chunk_overlap,
                        embeddings_model,
                        vectorstore_name,
                    )

                    if result["success"]:
                        st.success("Files uploaded successfully to RAG!")
                    else:
                        st.error(f"Upload failed: {result['error']}")

        st.divider()

        # MCP Tools Section
        st.subheader("MCP Tools")
        with st.expander("Available MCP Tools", expanded=False):
            try:
                # Get current user_id and chatbot_id from session state
                current_user_id = st.session_state.get('user_id', '')
                current_chatbot_id = st.session_state.get('chatbot_id', '')

                # Create a key that includes the IDs to refresh tools when IDs change
                tools_cache_key = f"mcp_tools_{current_user_id}_{current_chatbot_id}"

                # Get available tools
                if tools_cache_key not in st.session_state:
                    with st.spinner("Loading MCP tools..."):
                        st.session_state[tools_cache_key] = asyncio.run(
                            get_available_tools(current_user_id, current_chatbot_id)
                        )

                tools = st.session_state[tools_cache_key]

                if tools:
                    # Display current IDs being used
                    st.info(f"🔗 Using User ID: `{current_user_id[:8]}...` | Chatbot ID: `{current_chatbot_id[:8]}...`")

                    # Add refresh button
                    if st.button("🔄 Refresh Tools", help="Reload available MCP tools"):
                        with st.spinner("Refreshing MCP tools..."):
                            st.session_state[tools_cache_key] = asyncio.run(
                                get_available_tools(current_user_id, current_chatbot_id)
                            )
                            st.rerun()

                    st.write(f"**Found {len(tools)} available tools:**")

                    for i, tool in enumerate(tools, 1):
                        with st.expander(f"{i}. {tool.name}", expanded=False):
                            st.write(f"**Description:** {tool.description}")

                            # Get required parameters from inputSchema
                            if tool.inputSchema and 'properties' in tool.inputSchema:
                                required_params = tool.inputSchema.get('required', [])
                                properties = tool.inputSchema['properties']

                                st.write("**Parameters:**")

                                # Create input fields for each parameter
                                tool_args = {}
                                for param_name, param_info in properties.items():
                                    param_type = param_info.get('type', 'string')
                                    param_title = param_info.get('title', param_name)
                                    param_description = param_info.get('description', '')
                                    is_required = param_name in required_params

                                    label = f"{param_title} {'*' if is_required else ''}"
                                    help_text = param_description if param_description else None

                                    if param_type == 'string':
                                        value = st.text_input(
                                            label,
                                            key=f"mcp_{tool.name}_{param_name}",
                                            help=help_text
                                        )
                                        if value:
                                            tool_args[param_name] = value
                                    elif param_type == 'integer':
                                        value = st.number_input(
                                            label,
                                            key=f"mcp_{tool.name}_{param_name}",
                                            help=help_text,
                                            step=1
                                        )
                                        if value is not None:
                                            tool_args[param_name] = int(value)
                                    elif param_type == 'boolean':
                                        value = st.checkbox(
                                            label,
                                            key=f"mcp_{tool.name}_{param_name}",
                                            help=help_text
                                        )
                                        tool_args[param_name] = value

                                # Call tool button
                                if st.button(f"Call {tool.name}", key=f"call_mcp_{tool.name}"):
                                    # Check if required parameters are provided
                                    missing_required = [param for param in required_params if param not in tool_args or not tool_args[param]]

                                    if missing_required:
                                        st.warning(f"Please fill in required parameters: {', '.join(missing_required)}")
                                    else:
                                        with st.spinner(f"Calling {tool.name}..."):
                                            try:
                                                result = asyncio.run(calling_tools(
                                                    tool.name, tool_args, current_user_id, current_chatbot_id
                                                ))
                                                parsed_result = parse_tool_result(result)

                                                if parsed_result["is_error"]:
                                                    st.error("Tool execution failed!")
                                                    if parsed_result.get("main_result"):
                                                        st.error(f"Error details: {parsed_result['main_result']}")
                                                else:
                                                    st.success("Tool executed successfully!")

                                                # Display the main result
                                                if parsed_result.get("main_result"):
                                                    st.success("**Result:**")
                                                    st.code(parsed_result["main_result"], language="text")
                                                else:
                                                    st.info("No result returned")

                                            except Exception as e:
                                                st.error(f"Error calling tool: {str(e)}")
                            else:
                                st.info("This tool has no parameters.")

                                # Call tool button for parameterless tools
                                if st.button(f"🔧 Call {tool.name}", key=f"call_mcp_{tool.name}"):
                                    with st.spinner(f"Calling {tool.name}..."):
                                        try:
                                            result = asyncio.run(calling_tools(
                                                tool.name, {}, current_user_id, current_chatbot_id
                                            ))
                                            parsed_result = parse_tool_result(result)

                                            if parsed_result["is_error"]:
                                                st.error("Tool execution failed!")
                                                if parsed_result.get("main_result"):
                                                    st.error(f"Error details: {parsed_result['main_result']}")
                                            else:
                                                st.success("Tool executed successfully!")

                                            # Display the main result
                                            if parsed_result.get("main_result"):
                                                st.success("**Result:**")
                                                st.code(parsed_result["main_result"], language="text")
                                            else:
                                                st.info("No result returned")

                                        except Exception as e:
                                            st.error(f"Error calling tool: {str(e)}")
                else:
                    st.warning("No MCP tools available")

            except Exception as e:
                st.error(f"Error loading MCP tools: {str(e)}")
                if st.button("🔄 Retry Loading Tools"):
                    # Clear the cache for current IDs
                    current_user_id = st.session_state.get('user_id', '')
                    current_chatbot_id = st.session_state.get('chatbot_id', '')
                    tools_cache_key = f"mcp_tools_{current_user_id}_{current_chatbot_id}"
                    if tools_cache_key in st.session_state:
                        del st.session_state[tools_cache_key]
                    st.rerun()


def main():
    """Main application"""
    initialize_session_state()

    # App title
    st.title("MCP Chatbot Interface")
    st.markdown(
        "Chat with your AI assistant. Upload files using the sidebar to enhance the chatbot's knowledge."
    )

    # Render sidebar
    render_sidebar()

    # Main chat interface
    st.subheader("Chat")

    # Display chat history
    if st.session_state.chat_history:
        st.markdown("**Conversation History:**")
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.markdown(f"**You ({message['timestamp']}):**")
                st.info(message["content"])
            else:
                st.markdown(f"**Assistant ({message['timestamp']}):**")
                st.success(message["content"])
        st.divider()

    # Query input
    query = st.text_area(
        "Enter your message:",
        height=100,
        placeholder="Ask me anything! I can help with knowledge base queries, translations, and summarizations...",
    )

    # Submit and Clear buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        submit_button = st.button(
            "Send Message", type="primary", use_container_width=True
        )
    with col2:
        if st.button("Clear History", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    # Handle message submission
    if submit_button and query.strip():
        # Add user message to history
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.chat_history.append(
            {"role": "user", "content": query, "timestamp": timestamp}
        )

        # Make API request
        with st.spinner("Processing your message..."):
            result = make_chat_request(
                query, st.session_state.user_id, st.session_state.chatbot_id
            )

            if result["success"]:
                response_content = result["data"].get(
                    "response", "No response received"
                )
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": response_content,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    }
                )
                st.rerun()
            else:
                st.error(f"Error: {result['error']}")

    # Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"User ID: {st.session_state.user_id[:8]}...")
    with col2:
        st.caption(f"Chatbot ID: {st.session_state.chatbot_id[:8]}...")
    with col3:
        st.caption(f"Messages: {len(st.session_state.chat_history)}")


if __name__ == "__main__":
    main()
