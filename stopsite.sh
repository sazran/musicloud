#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

PID_FILE="${PID_FILE:-site.pid}"
PORT="${PORT:-5000}"
STOPPED=0

stop_pid() {
  PID="$1"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "Stopping site process PID $PID"
    kill "$PID" 2>/dev/null || true
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
      echo "PID $PID still running; forcing stop"
      kill -9 "$PID" 2>/dev/null || true
    fi
    STOPPED=1
  fi
}

if [ -f "$PID_FILE" ]; then
  stop_pid "$(cat "$PID_FILE")"
  rm -f "$PID_FILE"
fi

PIDS=$(pgrep -f "gunicorn .*:$PORT .*app:app|flask run .*--port $PORT" 2>/dev/null || true)
for PID in $PIDS; do
  if [ "$PID" != "$$" ]; then
    stop_pid "$PID"
  fi
done

if [ "$STOPPED" -eq 0 ]; then
  echo "No running site process found"
else
  echo "Site stopped"
fi
