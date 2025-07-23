import streamlit as st
import asyncio
import os
import sys
from typing import Dict, Any, List, Generator
from datetime import datetime
import json
import threading
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project source to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Fix for Windows asyncio compatibility with psycopg
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from rag_cag_agent.cag_rag_mcp import KnowledgeBase
from langchain_openai import ChatOpenAI
from translation.translation import translate_text
from summarization.summarization import text_summarization
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
        self.agent_responses = []
        self.tool_calls = []
        self.errors = []
        self.is_complete = False

def pre_model_hook(state):
    """Pre-model hook for message trimming"""
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=50000,
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed_messages}

def run_agent_streaming(query: str, user_id: str, chatbot_id: str, result_container: StreamingResult):
    """Run agent streaming in a separate thread"""
    async def stream_agent():
        try:
            logger.info(f"Starting agent streaming for user_id: {user_id}, chatbot_id: {chatbot_id}")
            
            # Create KnowledgeBase instance
            get_knowledge_base = KnowledgeBase(chatbot_id=chatbot_id, user_id=user_id)
            
            # Define tools
            tools = [
                translate_text,
                text_summarization,
                get_knowledge_base.get_knowledge_base,
            ]
            
            # Initialize LLM
            llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.5)
            
            config = {"configurable": {"thread_id": f"{user_id}"}}
            
            # Database connection - validate environment variables first
            required_env_vars = ['PG_USER_NAME', 'PG_PASSWORD', 'PG_HOST', 'PG_PORT', 'PG_NAME']
            missing_vars = [var for var in required_env_vars if not os.getenv(var)]
            
            logger.info(f"Environment check - Missing vars: {missing_vars}")
            
            if missing_vars:
                raise ValueError(f"Missing required environment variables: {missing_vars}")
            
            DB_URI = f"postgresql://{os.getenv('PG_USER_NAME')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_NAME')}?sslmode=require&connect_timeout=300"
            
            logger.info(f"Database URI constructed (password masked): postgresql://{os.getenv('PG_USER_NAME')}:***@{os.getenv('PG_HOST')}:{os.getenv('PG_PORT')}/{os.getenv('PG_NAME')}")
            
            if not DB_URI or "None" in DB_URI:
                raise ValueError(f"Database connection string contains None values: {DB_URI}")
                
            async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
                # Create the react agent
                agent = create_react_agent(
                    pre_model_hook=pre_model_hook,
                    model=llm,
                    tools=tools,
                    prompt=SYS_PROMPT_SUPERVISOR_AGENT,
                    checkpointer=checkpointer,
                )
                
                # Stream responses
                logger.info("Starting agent stream processing")
                async for message in agent.astream(
                    {"messages": [{"role": "user", "content": query}]}, config
                ):
                    logger.debug(f"Received message: {type(message)}, keys: {list(message.keys()) if isinstance(message, dict) else 'Not a dict'}")
                    
                    # Safely check if message is a dictionary
                    if not isinstance(message, dict) or message is None:
                        logger.warning(f"Skipping invalid message: {type(message)}")
                        continue
                        
                    # Process different types of messages
                    if "agent" in message and message["agent"] is not None:
                        agent_data = message["agent"]
                        if isinstance(agent_data, dict):
                            messages = agent_data.get("messages", [])
                            if isinstance(messages, list):
                                for msg in messages:
                                    if hasattr(msg, 'content') and msg.content:
                                        result_container.agent_responses.append({
                                            "content": msg.content,
                                            "timestamp": datetime.now().strftime("%H:%M:%S")
                                        })
                                        result_container.steps.append({
                                            "type": "agent_response",
                                            "content": msg.content,
                                            "timestamp": datetime.now().strftime("%H:%M:%S")
                                        })
                                
                    elif "tools" in message and message["tools"] is not None:
                        tool_data = message["tools"]
                        if isinstance(tool_data, dict):
                            tool_messages = tool_data.get("messages", [])
                            if isinstance(tool_messages, list):
                                for tool_msg in tool_messages:
                                    if hasattr(tool_msg, 'name'):
                                        tool_info = {
                                            "name": tool_msg.name,
                                            "content": str(tool_msg.content) if hasattr(tool_msg, 'content') else "",
                                            "timestamp": datetime.now().strftime("%H:%M:%S")
                                        }
                                        result_container.tool_calls.append(tool_info)
                                        result_container.steps.append({
                                            "type": "tool_execution",
                                            "tool_name": tool_msg.name,
                                            "content": str(tool_msg.content) if hasattr(tool_msg, 'content') else "",
                                            "timestamp": datetime.now().strftime("%H:%M:%S")
                                        })
                
                result_container.is_complete = True
                    
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            result_container.errors.append(error_msg)
            result_container.is_complete = True

    # Run in new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(stream_agent())
    finally:
        loop.close()

def display_streaming_results(result_container: StreamingResult, status_placeholder, steps_container, response_container):
    """Display streaming results in real-time"""
    
    # Show current status
    if result_container.errors:
        status_placeholder.error(f"{result_container.errors[-1]}")
    elif result_container.is_complete:
        status_placeholder.success("Query processed successfully!")
    else:
        status_placeholder.info("Processing your query...")
    
    # Display steps
    with steps_container:
        if result_container.steps:
            st.markdown("**Processing Steps:**")
            for i, step in enumerate(result_container.steps):
                if step["type"] == "tool_execution":
                    st.markdown(f"**Step {i+1}:** Tool Execution - `{step['tool_name']}` at {step['timestamp']}")
                    if step["content"]:
                        with st.expander(f"Tool Output - {step['tool_name']}", expanded=False):
                            st.code(step["content"], language="json")
                elif step["type"] == "agent_response":
                    st.markdown(f"**Step {i+1}:** Agent Response at {step['timestamp']}")
    
    # Display final response
    with response_container:
        if result_container.agent_responses:
            st.markdown("**Agent Response:**")
            for response in result_container.agent_responses:
                st.markdown(f"*{response['timestamp']}:*")
                st.markdown(response["content"])
                st.divider()

def main():
    """Main Streamlit application"""
    
    # Title and description
    st.title("MCP Agent Real-time Streaming")
    st.markdown("**Real-time streaming interface for the MCP Agent with intermediate steps visualization**")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # User inputs
        user_id = st.text_input(
            "User ID", 
            value="streamlit_user_123",
            help="Unique identifier for the user session"
        )
        
        chatbot_id = st.text_input(
            "Chatbot ID", 
            value="1568de36-660b-11f0-9fe2-0242ac120002",
            help="Chatbot instance identifier"
        )
        
        # Auto-refresh settings (hardcoded)
        auto_refresh = True
        refresh_interval = 1.0
        
        # Environment status
        # st.header("🔧 Environment Status")
        # env_vars = ['PG_USER_NAME', 'PG_PASSWORD', 'PG_HOST', 'PG_PORT', 'PG_NAME', 'OPENAI_API_KEY']
        # for var in env_vars:
        #     if os.getenv(var):
        #         st.success(f"✅ {var}")
        #     else:
        #         st.error(f"❌ {var}")
    
    # Initialize session state
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'streaming_result' not in st.session_state:
        st.session_state.streaming_result = None
    if 'streaming_thread' not in st.session_state:
        st.session_state.streaming_thread = None
    
    # Main interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("Query Input")
        
        # Query input
        query = st.text_area(
            "Enter your query:",
            height=100,
            placeholder="Ask me anything about the knowledge base, request translations, or summarizations..."
        )
        
        # Buttons
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submit_button = st.button("Submit Query", type="primary", use_container_width=True)
        with col_btn2:
            if st.button("Clear History", use_container_width=True):
                st.session_state.chat_history = []
                st.session_state.streaming_result = None
                st.session_state.streaming_thread = None
                st.rerun()
        
        # Display chat history
        if st.session_state.chat_history:
            st.header("Chat History")
            for i, chat_item in enumerate(reversed(st.session_state.chat_history[-5:])):  # Show last 5
                with st.expander(f"{chat_item['role'].title()} - {chat_item['timestamp']}", expanded=False):
                    if chat_item['role'] == 'user':
                        st.markdown(f"**Query:** {chat_item['content']}")
                    else:
                        st.markdown(f"**Response:** {chat_item['content']}")
                        if 'tool_calls' in chat_item and chat_item['tool_calls']:
                            st.markdown("**Tools Used:**")
                            for tool in chat_item['tool_calls']:
                                st.markdown(f"- {tool['name']}")
    
    with col2:
        st.header("Real-time Streaming Results")
        
        # Create containers for display
        status_placeholder = st.empty()
        steps_container = st.container()
        response_container = st.container()
        
        if submit_button and query.strip():
            # Add user query to history
            st.session_state.chat_history.append({
                "role": "user",
                "content": query,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            
            # Initialize streaming result
            st.session_state.streaming_result = StreamingResult()
            
            # Start streaming in a separate thread
            st.session_state.streaming_thread = threading.Thread(
                target=run_agent_streaming,
                args=(query, user_id, chatbot_id, st.session_state.streaming_result)
            )
            st.session_state.streaming_thread.start()
            
            # Display user query
            st.markdown(f"**You ({datetime.now().strftime('%H:%M:%S')}):**")
            st.markdown(query)
            st.divider()
        
        # Display streaming results if available
        if st.session_state.streaming_result:
            display_streaming_results(
                st.session_state.streaming_result, 
                status_placeholder, 
                steps_container, 
                response_container
            )
            
            # Auto-refresh logic
            if auto_refresh and not st.session_state.streaming_result.is_complete:
                time.sleep(refresh_interval)
                st.rerun()
            
            # Save to chat history when complete
            if st.session_state.streaming_result.is_complete and st.session_state.streaming_result.agent_responses:
                response_text = " ".join([r["content"] for r in st.session_state.streaming_result.agent_responses])
                if response_text and not any(chat['role'] == 'assistant' and chat['content'] == response_text for chat in st.session_state.chat_history):
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response_text,
                        "tool_calls": st.session_state.streaming_result.tool_calls,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
    
    # Footer
    st.markdown("---")
    st.markdown("**MCP Agent Streaming Interface** - Real-time AI Assistant with Tool Integration")

if __name__ == "__main__":
    main()
