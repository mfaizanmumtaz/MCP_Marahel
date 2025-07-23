#!/usr/bin/env python3
"""
Simple launcher script for the MCP Agent Streamlit application
"""

import subprocess
import sys
import os

def main():
    """Run the Streamlit application"""
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    streamlit_file = os.path.join(current_dir, "mcp_streamlit_v1.py")
    
    # Check if the file exists
    if not os.path.exists(streamlit_file):
        print(f"Error: {streamlit_file} not found!")
        sys.exit(1)
    
    # Run streamlit
    print("Starting MCP Agent Streamlit application...")
    print(f"Running: streamlit run {streamlit_file}")
    print("The application will open in your default web browser.")
    print("To stop the application, press Ctrl+C in this terminal.")
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", streamlit_file,
            "--server.port", "8501",
            "--server.address", "localhost"
        ], check=True)
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"Error running Streamlit: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: Streamlit not found. Please install it using: pip install streamlit")
        sys.exit(1)

if __name__ == "__main__":
    main() 