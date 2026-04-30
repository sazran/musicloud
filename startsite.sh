#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5173}"
PID_FILE="${PID_FILE:-site.pid}"
LOG_DIR="${LOG_DIR:-logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/site.log}"

find_python() {
  for NAME in python python3 py; do
    CANDIDATE=$(command -v "$NAME" 2>/dev/null || true)
    if [ -n "$CANDIDATE" ] && "$CANDIDATE" --version >/dev/null 2>&1; then
      printf '%s\n' "$CANDIDATE"
      return 0
    fi
  done
  return 1
}

if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Musicloud is already running with PID $OLD_PID"
    echo "Open http://$HOST:$PORT/"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

PYTHON_BIN=$(find_python || true)
if [ -z "$PYTHON_BIN" ]; then
  echo "Python was not found. Install Python or start a static server manually." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"

nohup "$PYTHON_BIN" -m http.server "$PORT" --bind "$HOST" >"$LOG_FILE" 2>&1 &

SITE_PID=$!
echo "$SITE_PID" > "$PID_FILE"

sleep 1
if ! kill -0 "$SITE_PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "Musicloud failed to start. See $SCRIPT_DIR/$LOG_FILE" >&2
  exit 1
fi

echo "Musicloud started with PID $SITE_PID"
echo "Open http://$HOST:$PORT/"
echo "Logs: $SCRIPT_DIR/$LOG_FILE"
