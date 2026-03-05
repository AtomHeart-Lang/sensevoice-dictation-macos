#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

chmod +x \
  ./install.sh \
  ./start_app.sh \
  ./create_launcher.sh \
  ./launch_from_desktop.sh \
  ./remove_launcher.sh \
  ./enable_autostart.sh \
  ./disable_autostart.sh \
  ./uninstall.sh \
  ./prepare_release.sh

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

PYTHON_BIN=""

python_ok() {
  local py="$1"
  "$py" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

if command -v python3 >/dev/null 2>&1 && python_ok "$(command -v python3)"; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[Step] Python 3.11+ not found. Trying to install via Homebrew."
  if ! command -v brew >/dev/null 2>&1; then
    echo "[ERROR] Homebrew is required for automatic Python installation."
    echo "Install Homebrew first: https://brew.sh"
    echo "Then rerun: ./install.sh"
    exit 1
  fi

  if ! brew list --versions python@3.11 >/dev/null 2>&1; then
    brew install python@3.11 || brew install python
  else
    brew upgrade python@3.11 || true
  fi

  if command -v python3 >/dev/null 2>&1 && python_ok "$(command -v python3)"; then
    PYTHON_BIN="$(command -v python3)"
  elif [[ -x /opt/homebrew/opt/python@3.11/bin/python3.11 ]] && python_ok /opt/homebrew/opt/python@3.11/bin/python3.11; then
    PYTHON_BIN="/opt/homebrew/opt/python@3.11/bin/python3.11"
  elif [[ -x /usr/local/opt/python@3.11/bin/python3.11 ]] && python_ok /usr/local/opt/python@3.11/bin/python3.11; then
    PYTHON_BIN="/usr/local/opt/python@3.11/bin/python3.11"
  fi
fi

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[ERROR] Python 3.11+ installation/lookup failed."
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit('[ERROR] Python 3.11+ required')
print('[OK] Python version:', sys.version.split()[0])
PY

if [[ ! -d .venv ]]; then
  echo "[Step] Creating virtual environment (.venv)"
  "$PYTHON_BIN" -m venv .venv
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
  echo "[Step] Downloading/refreshing Fun-ASR-Nano-2512 model cache"
python - <<'PY'
from funasr import AutoModel

errors = []
for trust_remote_code, remote_code in ((True, "./model.py"), (False, None)):
    kwargs = dict(
        model="FunAudioLLM/Fun-ASR-Nano-2512",
        trust_remote_code=trust_remote_code,
        vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
        disable_update=True,
    )
    if remote_code is not None:
        kwargs["remote_code"] = remote_code
    try:
        _ = AutoModel(**kwargs)
        break
    except Exception as exc:
        errors.append(f"trust_remote_code={trust_remote_code}: {exc!r}")
else:
    raise RuntimeError(
        "Model warmup failed. Ensure dependencies are installed (especially transformers/sentencepiece).\n"
        + "\n".join(errors)
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
