#!/bin/bash
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT/backend"

echo "📡 Starting FastAPI backend..."
echo ""

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run './scripts/setup.sh' first."
    exit 1
fi

source .venv/bin/activate

# Run server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

