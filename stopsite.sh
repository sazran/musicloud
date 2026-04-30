#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5173}"
PID_FILE="${PID_FILE:-site.pid}"
STOPPED=0

stop_pid() {
  PID="$1"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "Stopping Musicloud process PID $PID"
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

PIDS=$(pgrep -f "http.server $PORT --bind $HOST" 2>/dev/null || true)
for PID in $PIDS; do
  if [ "$PID" != "$$" ]; then
    stop_pid "$PID"
  fi
done

if [ "$STOPPED" -eq 0 ]; then
  echo "No running Musicloud process found on http://$HOST:$PORT/"
else
  echo "Musicloud stopped"
fi
