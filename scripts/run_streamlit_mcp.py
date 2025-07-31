#!/usr/bin/env python3
"""
Runner script for the MCP Agent Streamlit application
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Run the MCP Agent Streamlit application"""
    # Get the project root directory
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent
    app_file = project_root / "apps" / "streamlit_mcp_agent.py"
    
    # Check if the file exists
    if not app_file.exists():
        print(f"Error: {app_file} not found!")
        sys.exit(1)
    
    # Change to project root directory
    os.chdir(project_root)
    
    print("Starting MCP Agent Streamlit Application...")
    print(f"App file: {app_file}")
    print("=" * 50)
    
    try:
        # Run streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(app_file),
            "--server.port", "8502",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ]
        
        print("Command:", " ".join(cmd))
        print("=" * 50)
        print("Access the app at: http://localhost:8502")
        print("Make sure your MCP servers are running:")
        print("- Translation & Summarization: http://127.0.0.1:8001/mcp")
        print("- Knowledge Base: http://127.0.0.1:8003")
        print("=" * 50)
        
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Error running Streamlit: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
        sys.exit(0)
    except FileNotFoundError:
        print("Error: Streamlit not found. Please install it using: pip install streamlit")
        sys.exit(1)

if __name__ == "__main__":
    main()
