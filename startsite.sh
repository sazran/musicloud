#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
WORKERS="${WEB_CONCURRENCY:-2}"
PID_FILE="${PID_FILE:-site.pid}"
LOG_DIR="${LOG_DIR:-logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/site.log}"

if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Site is already running with PID $OLD_PID"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

mkdir -p "$LOG_DIR"

if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$VENV_DIR/bin/activate"
fi

export FLASK_APP="${FLASK_APP:-app.py}"

if command -v gunicorn >/dev/null 2>&1; then
  nohup gunicorn \
    --bind "$HOST:$PORT" \
    --workers "$WORKERS" \
    --access-logfile "-" \
    --error-logfile "-" \
    app:app >"$LOG_FILE" 2>&1 &
  SITE_PID=$!
else
  echo "gunicorn is not installed; falling back to Flask development server" >>"$LOG_FILE"
  nohup flask run --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
  SITE_PID=$!
fi

echo "$SITE_PID" > "$PID_FILE"
echo "Site started with PID $SITE_PID"
echo "Listening on http://$HOST:$PORT"
echo "Logs: $SCRIPT_DIR/$LOG_FILE"
