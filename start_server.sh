#!/bin/bash
# Start the PTC Agent server

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: .venv directory not found. Please run 'uv sync' first."
    exit 1
fi

# Set database environment variables if not already set
export DB_TYPE="${DB_TYPE:-postgres}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-postgres}"
export DB_USER="${DB_USER:-postgres}"
export DB_PASSWORD="${DB_PASSWORD:-postgres}"

# Check if required environment variables are set
if [ -z "$DAYTONA_API_KEY" ]; then
    echo "⚠️  Warning: DAYTONA_API_KEY is not set. The server may not work properly."
    echo "   Please set it in your .env file or export it:"
    echo "   export DAYTONA_API_KEY=your-key-here"
    echo ""
fi

# Start the server
echo "🚀 Starting PTC Agent server on http://localhost:8000"
echo "   Press Ctrl+C to stop the server"
echo ""

python server.py
