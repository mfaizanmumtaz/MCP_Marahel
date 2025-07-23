import streamlit as st
import requests
import uuid
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import os
import sys

# Add project source to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Streamlit page configuration
st.set_page_config(
    page_title="MCP Chatbot Interface",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Global configuration
API_BASE_URL = "http://localhost:8000/api"

# Initialize session state
def initialize_session_state():
    """Initialize session state variables"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    
    if 'chatbot_id' not in st.session_state:
        st.session_state.chatbot_id = str(uuid.uuid4())
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

def make_chat_request(query: str, user_id: str, chatbot_id: str) -> Dict:
    """Make request to chatbot API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat-bot",
            json={
                "query": query,
                "user_id": user_id,
                "chatbot_id": chatbot_id
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection Error: {str(e)}"}

def upload_files_cag(files, chatbot_id: str, llm: str, session_id: str = None) -> Dict:
    """Upload files to CAG ingestion API"""
    try:
        files_data = []
        form_data = {
            "chatbot_id": chatbot_id,
            "llm": llm
        }
        
        if session_id:
            form_data["session_id"] = session_id
        
        for file in files:
            files_data.append(("files", (file.name, file.getvalue(), file.type)))
        
        response = requests.post(
            f"{API_BASE_URL}/cag-ingestion",
            data=form_data,
            files=files_data,
            timeout=120
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"Upload Error: {response.status_code} - {response.text}"}
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection Error: {str(e)}"}

def upload_files_rag(files, chatbot_id: str, llm: str, chunk_size: int, 
                     chunk_overlap: int, embeddings_model: str, vectorstore_name: str) -> Dict:
    """Upload files to RAG ingestion API"""
    try:
        files_data = []
        form_data = {
            "chatbot_id": chatbot_id,
            "llm": llm,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "embeddings_model": embeddings_model,
            "vectorstore_name": vectorstore_name
        }
        
        for file in files:
            files_data.append(("files", (file.name, file.getvalue(), file.type)))
        
        response = requests.post(
            f"{API_BASE_URL}/rag-ingestion",
            data=form_data,
            files=files_data,
            timeout=120
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"Upload Error: {response.status_code} - {response.text}"}
    
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection Error: {str(e)}"}

def render_sidebar():
    """Render sidebar with ingestion APIs"""
    with st.sidebar:
        st.header("File Ingestion")
        
        # User and Chatbot ID management
        st.subheader("Configuration")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_input("User ID", value=st.session_state.user_id, disabled=True, key="display_user_id")
        with col2:
            if st.button("New User", help="Generate new User ID"):
                st.session_state.user_id = str(uuid.uuid4())
                st.rerun()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_input("Chatbot ID", value=st.session_state.chatbot_id, disabled=True, key="display_chatbot_id")
        with col2:
            if st.button("New Bot", help="Generate new Chatbot ID"):
                st.session_state.chatbot_id = str(uuid.uuid4())
                st.session_state.chat_history = []  # Clear history with new bot
                st.rerun()
        
        st.divider()
        
        # CAG Ingestion
        st.subheader("CAG Ingestion")
        with st.expander("Upload Files for CAG", expanded=False):
            cag_files = st.file_uploader(
                "Choose files for CAG",
                accept_multiple_files=True,
                type=["pdf", "docx", "doc", "csv", "xlsx"],
                key="cag_files"
            )
            
            cag_llm = st.selectbox("LLM Model", ["openai", "claude"], key="cag_llm")
            # cag_session_id = st.text_input("Session ID (Optional)", key="cag_session_id")
            
            if st.button("Upload to CAG", disabled=not cag_files):
                with st.spinner("Uploading files to CAG..."):
                    result = upload_files_cag(cag_files, st.session_state.chatbot_id, cag_llm)
                    
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
                key="rag_files"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                rag_llm = st.selectbox("LLM Model", ["openai", "claude"], key="rag_llm")
                chunk_size = st.number_input("Chunk Size", value=1000, min_value=100, max_value=2000, key="chunk_size")
            with col2:
                chunk_overlap = st.number_input("Chunk Overlap", value=200, min_value=0, max_value=500, key="chunk_overlap")
                embeddings_model = st.selectbox("Embeddings Model", ["openai"], key="embeddings_model")
            
            vectorstore_name = st.selectbox("Vector Store", ["pgvector","qdrant"], key="vectorstore_name")
            
            if st.button("Upload to RAG", disabled=not rag_files):
                with st.spinner("Uploading files to RAG..."):
                    result = upload_files_rag(
                        rag_files, st.session_state.chatbot_id, rag_llm, 
                        chunk_size, chunk_overlap, embeddings_model, vectorstore_name
                    )
                    
                    if result["success"]:
                        st.success("Files uploaded successfully to RAG!")
                    else:
                        st.error(f"Upload failed: {result['error']}")

def main():
    """Main application"""
    initialize_session_state()
    
    # App title
    st.title("MCP Chatbot Interface")
    st.markdown("Chat with your AI assistant. Upload files using the sidebar to enhance the chatbot's knowledge.")
    
    # Render sidebar
    render_sidebar()
    
    # Main chat interface
    st.subheader("Chat")
    
    # Display chat history
    if st.session_state.chat_history:
        st.markdown("**Conversation History:**")
        for i, message in enumerate(st.session_state.chat_history):
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
        placeholder="Ask me anything! I can help with knowledge base queries, translations, and summarizations..."
    )
    
    # Submit and Clear buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        submit_button = st.button("Send Message", type="primary", use_container_width=True)
    with col2:
        if st.button("Clear History", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    
    # Handle message submission
    if submit_button and query.strip():
        # Add user message to history
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.chat_history.append({
            "role": "user",
            "content": query,
            "timestamp": timestamp
        })
        
        # Make API request
        with st.spinner("Processing your message..."):
            result = make_chat_request(query, st.session_state.user_id, st.session_state.chatbot_id)
            
            if result["success"]:
                response_content = result["data"].get("response", "No response received")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response_content,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
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