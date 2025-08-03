#!/usr/bin/env python3
"""
Runner script for MCP servers
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    """Run the MCP servers"""
    # Get the project root directory
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent
    mcp_file = project_root / "src" / "run_mcp_servers.py"

    # Check if the file exists
    if not mcp_file.exists():
        print(f"Error: {mcp_file} not found!")
        sys.exit(1)

    # Change to project root directory
    os.chdir(project_root)

    print("Starting MCP Servers...")
    print(f"Running: python {mcp_file}")
    print("MCP servers will be available at:")
    print("- Translation & Summarization: http://127.0.0.1:8001/mcp")
    print("- Knowledge Base: http://127.0.0.1:8003")
    print("To stop the servers, press Ctrl+C in this terminal.")
    print("=" * 50)

    try:
        subprocess.run([sys.executable, str(mcp_file)], check=True)
    except KeyboardInterrupt:
        print("\nMCP servers stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"Error running MCP servers: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: Python not found. Please check your Python installation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
