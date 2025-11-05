#!/bin/bash
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Starting LungScan Assist development servers..."
echo ""
echo "This script runs both backend and frontend in parallel."
echo "You can also run them separately:"
echo "  ./scripts/dev_backend.sh   # Backend only"
echo "  ./scripts/dev_frontend.sh # Frontend only"
echo ""

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit
}

trap cleanup INT TERM

# Start backend
echo "📡 Starting FastAPI backend..."
cd "$PROJECT_ROOT/backend"
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run './scripts/setup.sh' first."
    exit 1
fi
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
cd "$PROJECT_ROOT"

# Wait a moment for backend to start
sleep 2

# Start frontend
echo "🌐 Starting Next.js frontend..."
cd "$PROJECT_ROOT/frontend"
if [ ! -d "node_modules" ]; then
    echo "❌ Node modules not found. Please run './scripts/setup.sh' first."
    exit 1
fi
npm run dev &
FRONTEND_PID=$!
cd "$PROJECT_ROOT"

echo ""
echo "✅ Servers starting..."
echo ""
echo "📍 Backend: http://127.0.0.1:8000"
echo "📍 Frontend: http://localhost:3000"
echo "📍 API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

