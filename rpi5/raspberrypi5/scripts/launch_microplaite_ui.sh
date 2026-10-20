#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$APP_DIR/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON:-python3}"
fi

export PYTHONPATH="$APP_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

AUTOSTART_LAUNCH=0
for argument in "$@"; do
  if [[ "$argument" == "--autostart" ]]; then
    AUTOSTART_LAUNCH=1
    break
  fi
done

if [[ "$AUTOSTART_LAUNCH" -eq 1 ]]; then
  LOG_DIR="$HOME/MicroplaiteData/logs"
  LOG_FILE="$LOG_DIR/autostart.log"
  mkdir -p "$LOG_DIR"
  {
    printf '\n[%s] Starting Microplaite Control:' "$(date -Is)"
    printf ' %q' "$@"
    printf '\n'
    exec "$PYTHON_BIN" "$APP_DIR/scripts/run_microplaite_ui.py" "$@"
  } >>"$LOG_FILE" 2>&1
fi

exec "$PYTHON_BIN" "$APP_DIR/scripts/run_microplaite_ui.py" "$@"
