#!/bin/sh
set -eu

uv run python main.py &
PIPELINE_PID=$!

cleanup() {
  kill "$PIPELINE_PID" 2>/dev/null || true
}

trap cleanup INT TERM

uv run uvicorn app.api_server:app --host 0.0.0.0 --port 8000
STATUS=$?

cleanup
wait "$PIPELINE_PID" 2>/dev/null || true

exit "$STATUS"
