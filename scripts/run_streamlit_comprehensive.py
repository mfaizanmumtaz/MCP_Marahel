#!/usr/bin/env python3
"""
Runner script for the comprehensive Streamlit application
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    """Run the comprehensive Streamlit application"""
    # Get the project root directory
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent
    app_file = project_root / "apps" / "streamlit_comprehensive.py"

    # Check if the file exists
    if not app_file.exists():
        print(f"Error: {app_file} not found!")
        sys.exit(1)

    # Change to project root directory
    os.chdir(project_root)

    print("Starting Comprehensive Streamlit Application...")
    print(f"App file: {app_file}")
    print("=" * 50)

    try:
        # Run streamlit
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_file),
            "--server.port",
            "8501",
            "--server.address",
            "0.0.0.0",
            "--browser.serverAddress",
            "localhost",
            "--browser.gatherUsageStats",
            "false",
        ]

        print("Command:", " ".join(cmd))
        print("=" * 50)
        print("Access the app at: http://localhost:8501")
        print("Make sure your FastAPI server is running on http://localhost:8000")
        print("=" * 50)

        subprocess.run(cmd, check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error running Streamlit: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
        sys.exit(0)
    except FileNotFoundError:
        print(
            "Error: Streamlit not found. Please install it using: pip install streamlit"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
