#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DELETE_DIR=0
for arg in "$@"; do
  case "$arg" in
    --delete-project-dir) DELETE_DIR=1 ;;
    *)
      echo "[ERROR] Unknown argument: $arg"
      echo "Usage: ./uninstall.sh [--delete-project-dir]"
      exit 1
      ;;
  esac
done

PLISTS=(
  "$HOME/Library/LaunchAgents/com.lee.sensevoice.hotkey.plist"
  "$HOME/Library/LaunchAgents/com.lee.sensevoice.hotkey.mac.plist"
  "$HOME/Library/LaunchAgents/com.lee.sensevoice.menubar.plist"
)
MODEL_DIRS=(
  "$HOME/.cache/modelscope/hub/models/iic/SenseVoiceSmall"
  "$HOME/.cache/modelscope/hub/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
)

APP_BUNDLE="$HOME/Applications/SenseVoice Dictation.app"
DESKTOP_APP="$HOME/Desktop/SenseVoice Dictation.app"


echo "[Step] Disable launch agents"
for p in "${PLISTS[@]}"; do
  if [[ -f "$p" ]]; then
    launchctl unload "$p" >/dev/null 2>&1 || true
    rm -f "$p"
    echo "  - removed $p"
  fi
done

echo "[Step] Stop running process"
pkill -f "[m]enubar_dictation_app.py" >/dev/null 2>&1 || true
pkill -f "[s]tart_app.sh" >/dev/null 2>&1 || true
pkill -f "[s]tart_menubar_app.sh" >/dev/null 2>&1 || true
pkill -f "[m]ain.py" >/dev/null 2>&1 || true

echo "[Step] Remove launcher apps"
rm -rf "$APP_BUNDLE" "$DESKTOP_APP"

echo "[Step] Remove model cache"
for d in "${MODEL_DIRS[@]}"; do
  if [[ -d "$d" ]]; then
    rm -rf "$d"
    echo "  - removed $d"
  fi
done

echo "[Step] Remove runtime artifacts"
rm -rf "$APP_DIR/.venv" "$APP_DIR/__pycache__"
rm -f "$APP_DIR"/*.log
rm -f "$APP_DIR"/*.lock
rm -f "$APP_DIR/ui_settings.json"
rm -f "$APP_DIR/config.toml"
rm -f /tmp/sensevoice_menubar.log /tmp/sensevoice_menubar_debug.log

if [[ "$DELETE_DIR" -eq 1 ]]; then
  echo "[Step] Remove project directory"
  cd "$(dirname "$APP_DIR")"
  rm -rf "$APP_DIR"
fi

echo "[Done] Uninstall completed."
if [[ "$DELETE_DIR" -eq 0 ]]; then
  echo "[Hint] Add --delete-project-dir to remove the source directory too."
fi
