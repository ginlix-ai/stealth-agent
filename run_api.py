#!/usr/bin/env python3
"""
Run the FastAPI server for Open PTC Agent.

This script starts the REST API server on localhost:8080.

Usage:
    # Activate virtual environment first:
    source .venv/bin/activate
    python run_api.py

    # Or use uv run (no activation needed):
    uv run python run_api.py

    # Or use uvicorn directly:
    uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
"""

import sys
from pathlib import Path

# Add project root to path if needed
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import uvicorn
except ImportError:
    print("Error: uvicorn not found. Please activate the virtual environment:")
    print("  source .venv/bin/activate")
    print("\nOr install dependencies:")
    print("  uv sync")
    sys.exit(1)

if __name__ == "__main__":
    print("Starting Open PTC Agent API server...")
    print("API will be available at: http://localhost:8080")
    print("API documentation at: http://localhost:8080/docs")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",  # Listen on all interfaces
        port=8080,
        reload=True,  # Auto-reload on code changes (for development)
        log_level="info",
    )

