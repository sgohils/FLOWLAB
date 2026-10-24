#!/usr/bin/env bash
# ============================================================================
#  FLOWLAB - one command to install, check and run everything on macOS/Linux.
#
#  Everything runs locally.  The first analysis downloads the YOLO weights once.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

# --- 1. Arguments -------------------------------------------------------------
usage() {
  cat <<'USAGE'
  ./run.sh             start the API and the frontend dev server (default)
  ./run.sh install     install backend and frontend dependencies
  ./run.sh lint        ruff over backend/ plus the source encoding check
  ./run.sh test        run the backend test suite
  ./run.sh build       production build of the frontend
  ./run.sh check       everything: ruff, mypy, backend tests, source encoding,
                      frontend typecheck, frontend tests, frontend build
  ./run.sh doctor      check the environment only
  ./run.sh --help      this list
USAGE
}

CMD="start"
case "${1:-start}" in
  --help|-h|help) CMD="help" ;;
  start|install|lint|test|build|check|doctor) CMD="$1" ;;
  "")
    CMD="start"
    ;;
  *)
    printf 'unknown command: %s\n\n' "$1"
    usage >&2
    exit 2
    ;;
esac

if [ "$CMD" = "help" ]; then
  usage
  exit 0
fi

section() {
  printf '\n==== %s ==========================================================\n' "$1"
}

# --- 2. Find a Python that actually works -------------------------------------
# A candidate is only accepted if it runs *and* has pip.  The pip half is not
# paranoia: a half-created .venv contains a python that starts perfectly and
# then dies with a confusing ImportError three commands later, so "the file
# exists" is not the same as "the interpreter works".
PY=""
BROKEN_VENV=""

probe() {
  "$1" -c 'import sys' >/dev/null 2>&1 || return 1
  "$1" -m pip --version >/dev/null 2>&1 || return 1
  return 0
}

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && probe "$candidate"; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ] && [ -x ".venv/bin/python" ]; then
  if probe ".venv/bin/python"; then
    PY=".venv/bin/python"
  else
    BROKEN_VENV=".venv/bin/python (run ./run.sh install)"
  fi
fi

if [ -z "$PY" ]; then
  for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 && probe "$candidate"; then
      PY="$candidate"
      break
    fi
  done
fi

if [ -z "$PY" ]; then
  if [ -n "$BROKEN_VENV" ]; then
    printf '\nThe virtual environment in this repository is broken: %s\n' "$BROKEN_VENV"
    printf '  It starts, but it has no pip and no installed packages, so every\n'
    printf '  command below would fail with a confusing ImportError.\n\n'
    printf 'Fix it with:        ./run.sh install\n'
    printf 'or start over with: rm -rf .venv\n\n'
  else
    printf '\nPython 3.11 or newer was not found.\n'
    printf '  - install it from https://www.python.org/downloads/, or\n'
    printf '  - create a virtual environment:  python3 -m venv .venv\n\n'
  fi
  exit 1
fi

printf 'Using Python %s  (%s)\n' "$("$PY" -c 'import sys;print(sys.version.split()[0])')" "$PY"
if [ -n "$BROKEN_VENV" ]; then
  printf 'Ignored broken virtual environment: %s\n' "$BROKEN_VENV"
fi

# Node is only required by the commands that touch frontend/.  `doctor` and the
# backend gates have to keep working when the thing being diagnosed is Node.
case "$CMD" in
  doctor|lint|test) ;;
  *)
    if ! command -v node >/dev/null 2>&1; then
      printf '\nnode not found (need 20 or newer; see https://nodejs.org)\n'
      exit 1
    fi
    ;;
esac

# --- 3. Subcommands ----------------------------------------------------------
case "$CMD" in

  doctor)
    "$PY" -m backend.scripts.doctor
    ;;

  lint)
    section "lint - ruff"
    "$PY" -m ruff check backend
    section "lint - source encoding"
    "$PY" -m backend.scripts.check_encoding
    printf '\nLint passed.\n'
    ;;

  test)
    section "test - backend suite"
    "$PY" -m pytest backend/tests
    section "test - source encoding"
    "$PY" -m backend.scripts.check_encoding
    ;;

  build)
    section "build - frontend production bundle"
    (cd frontend && npm run build)
    printf '\nBuilt frontend/dist - the API serves it automatically when it exists.\n'
    ;;

  check)
    # mypy is here, not only in CI.  CONTRIBUTING.md promises that `check` runs
    # the same set of checks CI does, and that promise was false while mypy was
    # missing: a type error that fails .github/workflows/ci.yml passed locally.
    section "check 1/6 - ruff"
    "$PY" -m ruff check backend
    section "check 2/6 - mypy"
    "$PY" -m mypy
    section "check 3/6 - backend tests"
    "$PY" -m pytest backend/tests
    section "check 4/6 - source encoding"
    "$PY" -m backend.scripts.check_encoding
    section "check 5/6 - frontend type check and tests"
    (cd frontend && npm run typecheck && npm test)
    section "check 6/6 - frontend build"
    (cd frontend && npm run build)
    printf '\n============================================================\n'
    printf ' ALL CHECKS PASSED\n'
    printf '============================================================\n'
    ;;

  install)
    section "install - backend runtime dependencies"
    "$PY" -m pip install -r backend/requirements.txt
    section "install - backend development dependencies (pytest, ruff, mypy)"
    "$PY" -m pip install -r backend/requirements-dev.txt
    section "install - frontend dependencies"
    (cd frontend && npm install)
    printf '\nInstalled.  Next: ./run.sh doctor, then ./run.sh.\n'
    ;;

  start)
    printf '\nStarting FLOWLAB\n'
    printf '  API      http://127.0.0.1:8000  (docs at /docs)\n'
    printf '  Frontend http://127.0.0.1:5173\n'
    printf 'Press Ctrl+C to stop both.\n\n'
    "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
    API_PID=$!
    trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
    sleep 3
    (cd frontend && npm run dev)
    ;;
esac
