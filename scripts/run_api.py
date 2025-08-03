#!/usr/bin/env python3
"""
Runner script for the FastAPI server
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    """Run the FastAPI server"""
    # Get the project root directory
    current_dir = Path(__file__).parent.absolute()
    project_root = current_dir.parent
    main_file = project_root / "src" / "main.py"

    # Check if the file exists
    if not main_file.exists():
        print(f"Error: {main_file} not found!")
        sys.exit(1)

    # Change to project root directory
    os.chdir(project_root)

    print("Starting FastAPI Server...")
    print(f"Running: python {main_file}")
    print("The API will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("To stop the server, press Ctrl+C in this terminal.")
    print("=" * 50)

    try:
        subprocess.run([sys.executable, str(main_file)], check=True)
    except KeyboardInterrupt:
        print("\nFastAPI server stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"Error running FastAPI server: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: Python not found. Please check your Python installation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
