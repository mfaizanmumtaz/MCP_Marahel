#!/usr/bin/env python3
"""
Unified entry point for MCP_Marahel project
This script provides a simple interface to run different components of the system.
"""

import subprocess
import sys
from pathlib import Path


def run_api():
    """Run the FastAPI server"""
    script_path = Path(__file__).parent / "scripts" / "run_api.py"
    subprocess.run([sys.executable, str(script_path)])


def run_mcp_servers():
    """Run the MCP servers"""
    script_path = Path(__file__).parent / "scripts" / "run_mcp_servers.py"
    subprocess.run([sys.executable, str(script_path)])


def run_streamlit_comprehensive():
    """Run the comprehensive Streamlit app"""
    script_path = Path(__file__).parent / "scripts" / "run_streamlit_comprehensive.py"
    subprocess.run([sys.executable, str(script_path)])


def run_streamlit_mcp():
    """Run the MCP agent Streamlit app"""
    script_path = Path(__file__).parent / "scripts" / "run_streamlit_mcp.py"
    subprocess.run([sys.executable, str(script_path)])


def show_help():
    """Show available commands"""
    print("""
MCP_Marahel Project Runner
=========================

Available commands:
  api                    Run the FastAPI server (port 800)
  mcp                    Run the MCP servers (ports 8001)
  app                    Run the comprehensive Streamlit app (port 8501)
  agent                  Run the MCP agent Streamlit app (port 8502)
  help                   Show this help message

Usage examples:
  python run.py api      # Start the FastAPI server
  python run.py mcp      # Start MCP servers
  python run.py app      # Start comprehensive Streamlit app
  python run.py agent    # Start MCP agent Streamlit app

Typical startup sequence:
1. python run.py mcp     # Start MCP servers first
2. python run.py api     # Start FastAPI server
3. python run.py app     # Start Streamlit app

For development, you might want to run each in separate terminals.
""")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()

    commands = {
        "api": run_api,
        "mcp": run_mcp_servers,
        "app": run_streamlit_comprehensive,
        "agent": run_streamlit_mcp,
        "help": show_help,
        "--help": show_help,
        "-h": show_help,
    }

    if command in commands:
        commands[command]()
    else:
        print(f"Unknown command: {command}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
