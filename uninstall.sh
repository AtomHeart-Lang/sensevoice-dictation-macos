#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_LABEL="com.lee.sensevoice.menubar"
LAUNCH_DOMAIN="gui/$(id -u)"
AUTOSTART_DIR="$HOME/Library/Application Support/SenseVoiceDictation"
AUTOSTART_LOG_DIR="$HOME/Library/Logs/SenseVoiceDictation"
APP_SUPPORT_UI_SETTINGS="$AUTOSTART_DIR/ui_settings.json"
APP_SUPPORT_UI_SETTINGS_TMP="$AUTOSTART_DIR/ui_settings.json.tmp"
APP_SUPPORT_UI_SETTINGS_BROKEN="$AUTOSTART_DIR/ui_settings.json.broken"
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
  "$HOME/.cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512"
  "$HOME/.cache/modelscope/hub/models/iic/SenseVoiceSmall"
  "$HOME/.cache/modelscope/hub/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
)

APP_BUNDLE="$HOME/Applications/FunASR Dictation.app"
DESKTOP_APP="$HOME/Desktop/FunASR Dictation.app"
LEGACY_APP_BUNDLE="$HOME/Applications/SenseVoice Dictation.app"
LEGACY_DESKTOP_APP="$HOME/Desktop/SenseVoice Dictation.app"
TCC_IDS=(
  "com.lee.sensevoice.dictation.launcher"
  "com.lee.sensevoice.menubar"
)


echo "[Step] Disable launch agents"
launchctl bootout "$LAUNCH_DOMAIN/$LAUNCH_LABEL" >/dev/null 2>&1 || true
launchctl disable "$LAUNCH_DOMAIN/$LAUNCH_LABEL" >/dev/null 2>&1 || true
for p in "${PLISTS[@]}"; do
  if [[ -f "$p" ]]; then
    launchctl bootout "$LAUNCH_DOMAIN" "$p" >/dev/null 2>&1 || true
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
rm -rf "$LEGACY_APP_BUNDLE" "$LEGACY_DESKTOP_APP"

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
rm -f "$APP_DIR/menubar.out.log" "$APP_DIR/menubar.err.log"
rm -f "$APP_DIR"/*.lock
rm -f "$APP_DIR/ui_settings.json" "$APP_DIR/ui_settings.json.tmp" "$APP_DIR/ui_settings.json.broken"
rm -f "$APP_DIR/config.toml"
rm -f "$APP_SUPPORT_UI_SETTINGS" "$APP_SUPPORT_UI_SETTINGS_TMP" "$APP_SUPPORT_UI_SETTINGS_BROKEN"
rm -rf "$AUTOSTART_DIR" "$AUTOSTART_LOG_DIR"
rm -f /tmp/sensevoice_menubar.log /tmp/sensevoice_menubar_debug.log

echo "[Step] Reset TCC permissions (best effort)"
for id in "${TCC_IDS[@]}"; do
  tccutil reset All "$id" >/dev/null 2>&1 || true
  tccutil reset Accessibility "$id" >/dev/null 2>&1 || true
  tccutil reset ListenEvent "$id" >/dev/null 2>&1 || true
done

if [[ "$DELETE_DIR" -eq 1 ]]; then
  echo "[Step] Remove project directory"
  cd "$(dirname "$APP_DIR")"
  rm -rf "$APP_DIR"
fi

echo "[Done] Uninstall completed."
if [[ "$DELETE_DIR" -eq 0 ]]; then
  echo "[Hint] Add --delete-project-dir to remove the source directory too."
fi
