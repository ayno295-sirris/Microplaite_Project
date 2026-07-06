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
exec "$PYTHON_BIN" "$APP_DIR/scripts/run_microplaite_ui.py" "$@"
