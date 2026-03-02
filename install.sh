#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

WITH_MODEL=1
WITH_LAUNCHER=1
WITH_AUTOSTART=0

for arg in "$@"; do
  case "$arg" in
    --no-model) WITH_MODEL=0 ;;
    --no-launcher) WITH_LAUNCHER=0 ;;
    --autostart) WITH_AUTOSTART=1 ;;
    *)
      echo "[ERROR] Unknown argument: $arg"
      echo "Usage: ./install.sh [--no-model] [--no-launcher] [--autostart]"
      exit 1
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[ERROR] This installer only supports macOS."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found. Install Python 3.11+ first."
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit('[ERROR] Python 3.11+ required')
print('[OK] Python version:', sys.version.split()[0])
PY

if [[ ! -d .venv ]]; then
  echo "[Step] Creating virtual environment (.venv)"
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "[Step] Installing Python dependencies"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

if [[ ! -f config.toml ]]; then
  cp config.example.toml config.toml
  echo "[Step] Created config.toml from template"
fi

if [[ "$WITH_MODEL" -eq 1 ]]; then
  echo "[Step] Downloading/refreshing SenseVoice model cache"
  python - <<'PY'
from funasr import AutoModel

model = AutoModel(
    model="iic/SenseVoiceSmall",
    trust_remote_code=False,
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 30000},
    device="cpu",
    disable_update=True,
)
print('[OK] Model is ready')
PY
fi

if [[ "$WITH_LAUNCHER" -eq 1 ]]; then
  echo "[Step] Creating clickable launcher app"
  ./create_launcher.sh
fi

if [[ "$WITH_AUTOSTART" -eq 1 ]]; then
  echo "[Step] Enabling autostart"
  ./enable_autostart.sh
fi

echo "[Done] Installation completed."
echo "Run: ./start_app.sh"
