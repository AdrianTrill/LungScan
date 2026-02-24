#!/bin/bash
set -euo pipefail

echo "🚀 Setting up LungScan Assist..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Backend setup
echo ""
echo "📦 Setting up backend..."
cd apps/backend

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Backend setup complete!"

# Frontend setup
echo ""
echo "📦 Setting up frontend..."
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install
else
    echo "Node modules already installed, skipping..."
fi

echo "✅ Frontend setup complete!"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Copy apps/backend/.env.example to apps/backend/.env (if needed)"
echo "  2. Copy apps/frontend/.env.example to apps/frontend/.env.local (if needed)"
echo "  3. Run './scripts/dev.sh' to start both servers"
echo ""
