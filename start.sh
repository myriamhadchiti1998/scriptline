#!/usr/bin/env bash
# One-command local start (macOS / Linux): API on :8000, dashboard on :3000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── backend ──────────────────────────────────────────────────────────────────
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "→ creating Python virtualenv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠  Created backend/.env — put your ANTHROPIC_API_KEY in it, then re-run ./start.sh"
  exit 1
fi
echo "→ starting API on http://localhost:8000"
python -m uvicorn app.main:app --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

# ── frontend ─────────────────────────────────────────────────────────────────
cd "$ROOT/frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
echo "→ starting dashboard on http://localhost:3000"
npm run dev
