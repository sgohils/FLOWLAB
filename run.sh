#!/usr/bin/env bash
# FLOWLAB - one command to start everything on macOS or Linux.
#
#   ./run.sh            start the API and the frontend (default)
#   ./run.sh doctor     check the environment only
#   ./run.sh test       run the backend test suite
#   ./run.sh install    install backend and frontend dependencies
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 not found (need 3.11+)"; exit 1; }
command -v node >/dev/null || { echo "node not found (need 18+)"; exit 1; }

case "${1:-start}" in
  doctor)  exec python3 -m backend.scripts.doctor ;;
  test)
    python3 -m pytest backend/tests -q
    python3 -m backend.scripts.check_encoding
    ;;
  install)
    python3 -m pip install -r backend/requirements.txt
    (cd frontend && npm install)
    ;;
  start)
    echo
    echo "Starting FLOWLAB"
    echo "  API      http://127.0.0.1:8000  (docs at /docs)"
    echo "  Frontend http://127.0.0.1:5173"
    echo "Press Ctrl+C to stop both."
    echo
    python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
    API_PID=$!
    trap 'kill $API_PID 2>/dev/null || true' EXIT
    sleep 3
    (cd frontend && npm run dev)
    ;;
  *) echo "unknown command: $1"; exit 1 ;;
esac
