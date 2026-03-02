#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .venv/bin/activate ]]; then
  echo "[ERROR] .venv not found. Run ./install.sh first."
  exit 1
fi

# Single instance protection.
if pgrep -f "[m]enubar_dictation_app.py" >/dev/null 2>&1; then
  echo "[INFO] SenseVoice menubar app is already running."
  exit 0
fi

source .venv/bin/activate
exec python3 menubar_dictation_app.py
