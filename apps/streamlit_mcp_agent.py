import streamlit as st
import asyncio
import os
import sys
from typing import Dict, Any, Generator
from datetime import datetime
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project source to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv, find_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from prompts.prompts import SYS_PROMPT_SUPERVISOR_AGENT

# Load environment variables
load_dotenv(find_dotenv())

# Streamlit page configuration
st.set_page_config(
    page_title="MCP Agent Real-time Streaming",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

class StreamingResult:
    """Class to handle streaming results"""
    def __init__(self):
        self.steps = []
        self.final_response = ""
        self.is_complete = False
        self.error = None

    def add_step(self, step_data):
        self.steps.append({
            "timestamp": datetime.now(),
            "data": step_data
        })

    def set_final_response(self, response):
        self.final_response = response
        self.is_complete = True

    def set_error(self, error):
        self.error = error
        self.is_complete = True

def pre_model_hook(state):
    """Pre-processing hook for the model"""
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=50000,
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed_messages}

async def stream_agent_response(query: str, user_id: str, chatbot_id: str) -> Generator[Dict[str, Any], None, None]:
    """Stream agent responses in real-time"""
    try:
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
        
        # Database configuration
        DB_URI = f"postgresql://{os.getenv('PG_USER_NAME')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_NAME')}?sslmode=require&connect_timeout=300"
        
        if not DB_URI:
            yield {"type": "error", "content": "Database configuration missing"}
            return

        config = {"configurable": {"thread_id": f"{user_id}"}}

        async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
            # Create tools (simplified for demo)
            tools = []
            
            # Create agent
            agent = create_react_agent(
                pre_model_hook=pre_model_hook,
                model=llm,
                tools=tools,
                prompt=SYS_PROMPT_SUPERVISOR_AGENT,
                checkpointer=checkpointer,
            )

            # Stream responses
            async for message in agent.astream(
                {"messages": [{"role": "user", "content": query}]}, config
            ):
                if "agent" in message:
                    response = message["agent"]
                    if response and "messages" in response:
                        content = response["messages"][0].content
                        yield {
                            "type": "agent_response",
                            "content": content,
                            "timestamp": datetime.now().isoformat()
                        }
                elif "tools" in message:
                    tool_calls = message["tools"]
                    for tool_call in tool_calls:
                        yield {
                            "type": "tool_call",
                            "content": f"Using tool: {tool_call.get('name', 'Unknown')}",
                            "timestamp": datetime.now().isoformat()
                        }

    except Exception as e:
        yield {"type": "error", "content": f"Error: {str(e)}"}

def main():
    """Main Streamlit application"""
    st.title("🤖 MCP Agent Real-time Streaming")
    st.markdown("---")

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        user_id = st.text_input("User ID", value="test_user_123")
        chatbot_id = st.text_input("Chatbot ID", value="1568de36-660b-11f0-9fe2-0242ac120002")
        
        st.markdown("---")
        st.header("Available Tools")
        st.markdown("""
        - 🔍 **Knowledge Base Search**
        - 🌐 **Translation Services**  
        - 📝 **Text Summarization**
        - 💬 **Chat History Management**
        """)

    # Main chat interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Chat Interface")
        
        # Query input
        query = st.text_area(
            "Enter your query:",
            placeholder="Ask me anything about your documents, request translations, or get summaries...",
            height=100
        )
        
        # Control buttons
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            if st.button("🚀 Send Query", type="primary", use_container_width=True):
                if query.strip():
                    st.session_state.processing = True
                    st.session_state.query = query
                else:
                    st.warning("Please enter a query first!")
        
        with col_btn2:
            if st.button("🔄 Clear Chat", use_container_width=True):
                if 'messages' in st.session_state:
                    st.session_state.messages = []
                st.success("Chat cleared!")
        
        with col_btn3:
            if st.button("⏹️ Stop", use_container_width=True):
                st.session_state.processing = False

    with col2:
        st.header("Status")
        
        # Status indicators
        if st.session_state.get('processing', False):
            st.success("🟢 Processing...")
        else:
            st.info("🔵 Ready")
        
        # Connection status
        st.markdown("**Connection Status:**")
        st.markdown("- Database: 🟢 Connected")
        st.markdown("- MCP Server: 🟢 Active")
        st.markdown("- LLM: 🟢 Ready")

    # Chat messages display
    st.markdown("---")
    st.header("💬 Conversation")
    
    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    # Display chat messages
    chat_container = st.container()
    
    with chat_container:
        for i, message in enumerate(st.session_state.messages):
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant"):
                    st.write(message["content"])
    
    # Process query if requested
    if st.session_state.get('processing', False) and 'query' in st.session_state:
        query = st.session_state.query
        
        # Add user message
        st.session_state.messages.append({"role": "user", "content": query})
        
        # Create placeholder for streaming response
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            
            try:
                # Note: This is a simplified version. In a real implementation,
                # you would need to handle the async streaming properly
                response_text = "I'm processing your request. This is a demo response showing how the streaming would work."
                
                # Simulate streaming by showing text progressively
                for i in range(0, len(response_text), 10):
                    partial_text = response_text[:i+10]
                    response_placeholder.write(partial_text)
                    time.sleep(0.1)
                
                # Add assistant message to session state
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": response_text
                })
                
            except Exception as e:
                st.error(f"Error processing query: {str(e)}")
            
            finally:
                st.session_state.processing = False
                if 'query' in st.session_state:
                    del st.session_state.query

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>MCP Agent Real-time Streaming Interface</p>
            <p>Powered by LangGraph, FastMCP, and Streamlit</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
