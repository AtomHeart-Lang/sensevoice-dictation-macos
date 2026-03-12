#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

chmod +x \
  ./install.sh \
  ./start_app.sh \
  ./create_launcher.sh \
  ./create_desktop_shortcut.sh \
  ./create_uninstaller.sh \
  ./launch_from_desktop.sh \
  ./remove_launcher.sh \
  ./enable_autostart.sh \
  ./disable_autostart.sh \
  ./uninstall.sh \
  ./prepare_release.sh \
  ./build_dmg.sh \
  ./install_from_dmg.command \
  ./download_python_runtime.sh

WITH_MODEL=1
WITH_LAUNCHER=1
WITH_AUTOSTART=0

emit_progress() {
  local percent="$1"
  shift
  echo "[Progress] $percent $*"
}

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

if [[ -n "${SVD_PYTHON_BIN:-}" ]]; then
  if python_ok "$SVD_PYTHON_BIN"; then
    PYTHON_BIN="$SVD_PYTHON_BIN"
  else
    echo "[ERROR] SVD_PYTHON_BIN is set but invalid: $SVD_PYTHON_BIN"
    exit 1
  fi
fi

if [[ -z "$PYTHON_BIN" ]] && command -v python3 >/dev/null 2>&1 && python_ok "$(command -v python3)"; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "$PYTHON_BIN" ]]; then
  emit_progress 10 "Python 3.11+ not found, trying Homebrew"
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
  emit_progress 40 "Creating Python virtual environment"
  echo "[Step] Creating virtual environment (.venv)"
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

emit_progress 48 "Installing Python dependencies"
echo "[Step] Installing Python dependencies"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

if [[ ! -f config.toml ]]; then
  cp config.example.toml config.toml
  echo "[Step] Created config.toml from template"
fi

if [[ "$WITH_MODEL" -eq 1 ]]; then
  emit_progress 68 "Downloading latest model files"
  echo "[Step] Downloading/refreshing Fun-ASR-Nano-2512 model cache"
FUNASR_RUNTIME_DIR="$APP_DIR/funasr_nano_runtime"
if [[ ! -f "$FUNASR_RUNTIME_DIR/model.py" ]]; then
  echo "[ERROR] Missing runtime file: $FUNASR_RUNTIME_DIR/model.py"
  echo "Please ensure repository files are complete, then rerun ./install.sh"
  exit 1
fi
python - <<PY
import os
import sys
from funasr import AutoModel

runtime_dir = os.path.abspath("${FUNASR_RUNTIME_DIR}")
remote_code_path = os.path.join(runtime_dir, "model.py")
if runtime_dir not in sys.path:
    sys.path.insert(0, runtime_dir)

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
        kwargs["remote_code"] = remote_code_path
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
  emit_progress 86 "Creating launcher app"
  echo "[Step] Creating clickable launcher app"
  ./create_launcher.sh
fi

emit_progress 92 "Creating graphical uninstaller"
echo "[Step] Creating graphical uninstaller"
./create_uninstaller.sh

if [[ "$WITH_AUTOSTART" -eq 1 ]]; then
  emit_progress 96 "Enabling launch at login"
  echo "[Step] Enabling autostart"
  ./enable_autostart.sh
fi

emit_progress 100 "Installation completed"
echo "[Done] Installation completed."
echo "Run: ./start_app.sh"
