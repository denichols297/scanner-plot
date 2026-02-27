#!/usr/bin/env bash
# run.sh — Start the Scanner Plot web app
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$PROJECT_DIR/.venv"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           ⚡ SCANNER PLOT — STARTUP                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Virtual environment ──────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "📦 Installing/updating dependencies..."
pip install -q --upgrade pip
pip install -q -r "$BACKEND_DIR/requirements.txt"

# ── .env file ─────────────────────────────────────────────────
if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "⚙️  No .env found — copying .env.example (Demo Mode will be active)"
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

# ── Check for ffmpeg (needed for live mode only) ──────────────
if ! command -v ffmpeg &>/dev/null; then
  echo "⚠️  ffmpeg not found. Live stream mode requires ffmpeg."
  echo "   Install it with:  brew install ffmpeg"
  echo "   Continuing in Demo Mode regardless."
fi

echo ""
echo "🚀 Starting backend server..."
echo "   → Open http://localhost:5050 in your browser"
echo "   → Press Ctrl+C to stop"
echo ""

cd "$BACKEND_DIR"
python app.py
