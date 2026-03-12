#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_LABEL="com.lee.funasr.menubar"
LEGACY_LAUNCH_LABEL="com.lee.sensevoice.menubar"
LAUNCH_DOMAIN="gui/$(id -u)"
AUTOSTART_DIR="$HOME/Library/Application Support/SenseVoiceDictation"
AUTOSTART_LOG_DIR="$HOME/Library/Logs/SenseVoiceDictation"
STANDARD_INSTALL_ROOT="$HOME/Library/Application Support/FunASRDictation"
STANDARD_INSTALL_APP_DIR="$STANDARD_INSTALL_ROOT/app"
STANDARD_INSTALL_PYTHON_DIR="$STANDARD_INSTALL_ROOT/python-runtime"
RUNTIME_PATH_FILE="$AUTOSTART_DIR/runtime_app_dir.txt"
APP_SUPPORT_UI_SETTINGS="$AUTOSTART_DIR/ui_settings.json"
APP_SUPPORT_UI_SETTINGS_TMP="$AUTOSTART_DIR/ui_settings.json.tmp"
APP_SUPPORT_UI_SETTINGS_BROKEN="$AUTOSTART_DIR/ui_settings.json.broken"
DELETE_DIR=0
WARNINGS=()

emit_progress() {
  local percent="$1"
  shift
  echo "[Progress] $percent $*"
}

warn() {
  local message="$1"
  WARNINGS+=("$message")
  echo "[WARN] $message"
}

remove_path_best_effort() {
  local path="$1"
  local warning_message="$2"
  if [[ ! -e "$path" && ! -L "$path" ]]; then
    return 0
  fi
  if rm -rf "$path" >/dev/null 2>&1; then
    echo "  - removed $path"
    return 0
  fi
  warn "$warning_message"
}

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
  "$HOME/Library/LaunchAgents/com.lee.funasr.menubar.plist"
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
UNINSTALLER_APP="$HOME/Applications/Uninstall FunASR Dictation.app"
DESKTOP_APP="$HOME/Desktop/FunASR Dictation.app"
LEGACY_APP_BUNDLE="$HOME/Applications/SenseVoice Dictation.app"
LEGACY_DESKTOP_APP="$HOME/Desktop/SenseVoice Dictation.app"
TCC_IDS=(
  "com.lee.funasr.dictation.launcher"
  "com.lee.funasr.menubar"
  "com.lee.sensevoice.dictation.launcher"
  "com.lee.sensevoice.menubar"
)

emit_progress 8 "Disabling launch agents"
echo "[Step] Disable launch agents"
launchctl bootout "$LAUNCH_DOMAIN/$LAUNCH_LABEL" >/dev/null 2>&1 || true
launchctl disable "$LAUNCH_DOMAIN/$LAUNCH_LABEL" >/dev/null 2>&1 || true
launchctl bootout "$LAUNCH_DOMAIN/$LEGACY_LAUNCH_LABEL" >/dev/null 2>&1 || true
launchctl disable "$LAUNCH_DOMAIN/$LEGACY_LAUNCH_LABEL" >/dev/null 2>&1 || true
for p in "${PLISTS[@]}"; do
  if [[ -f "$p" ]]; then
    launchctl bootout "$LAUNCH_DOMAIN" "$p" >/dev/null 2>&1 || true
    launchctl unload "$p" >/dev/null 2>&1 || true
    rm -f "$p"
    echo "  - removed $p"
  fi
done
emit_progress 18 "Stopping running processes"
echo "[Step] Stop running process"
pkill -f "[m]enubar_dictation_app.py" >/dev/null 2>&1 || true
pkill -f "[s]tart_app.sh" >/dev/null 2>&1 || true
pkill -f "[s]tart_menubar_app.sh" >/dev/null 2>&1 || true
pkill -f "[m]ain.py" >/dev/null 2>&1 || true
emit_progress 30 "Removing launcher apps"
echo "[Step] Remove launcher apps"
remove_path_best_effort "$APP_BUNDLE" "Could not remove launcher app automatically: $APP_BUNDLE"
remove_path_best_effort "$UNINSTALLER_APP" "Could not remove graphical uninstaller automatically: $UNINSTALLER_APP"
remove_path_best_effort "$DESKTOP_APP" "Desktop shortcut could not be removed automatically: $DESKTOP_APP. Please delete it manually from Desktop."
remove_path_best_effort "$LEGACY_APP_BUNDLE" "Could not remove legacy launcher app automatically: $LEGACY_APP_BUNDLE"
remove_path_best_effort "$LEGACY_DESKTOP_APP" "Could not remove legacy Desktop shortcut automatically: $LEGACY_DESKTOP_APP. Please delete it manually from Desktop."
emit_progress 45 "Removing model cache"
echo "[Step] Remove model cache"
for d in "${MODEL_DIRS[@]}"; do
  if [[ -d "$d" ]]; then
    rm -rf "$d"
    echo "  - removed $d"
  fi
done
emit_progress 62 "Removing runtime files"
echo "[Step] Remove runtime artifacts"
rm -rf "$APP_DIR/.venv" "$APP_DIR/__pycache__"
rm -f "$APP_DIR"/*.log
rm -f "$APP_DIR/menubar.out.log" "$APP_DIR/menubar.err.log"
rm -f "$APP_DIR"/*.lock
rm -f "$APP_DIR/ui_settings.json" "$APP_DIR/ui_settings.json.tmp" "$APP_DIR/ui_settings.json.broken"
rm -f "$APP_DIR/config.toml"
rm -f "$RUNTIME_PATH_FILE"
rm -f "$APP_SUPPORT_UI_SETTINGS" "$APP_SUPPORT_UI_SETTINGS_TMP" "$APP_SUPPORT_UI_SETTINGS_BROKEN"
rm -rf "$AUTOSTART_DIR" "$AUTOSTART_LOG_DIR"
rm -rf "$STANDARD_INSTALL_PYTHON_DIR"
rm -f "$STANDARD_INSTALL_ROOT/install.log"
rmdir "$STANDARD_INSTALL_ROOT" >/dev/null 2>&1 || true
rm -f /tmp/sensevoice_menubar.log /tmp/sensevoice_menubar_debug.log
emit_progress 82 "Resetting macOS permissions"
echo "[Step] Reset TCC permissions (best effort)"
for id in "${TCC_IDS[@]}"; do
  tccutil reset All "$id" >/dev/null 2>&1 || true
  tccutil reset Accessibility "$id" >/dev/null 2>&1 || true
  tccutil reset ListenEvent "$id" >/dev/null 2>&1 || true
done

if [[ "$DELETE_DIR" -eq 1 ]]; then
  emit_progress 92 "Removing installed project directory"
  echo "[Step] Remove project directory"
  cd "$(dirname "$APP_DIR")"
  rm -rf "$APP_DIR"
  if [[ "$STANDARD_INSTALL_APP_DIR" != "$APP_DIR" ]]; then
    rm -rf "$STANDARD_INSTALL_APP_DIR"
  fi
  rm -rf "$STANDARD_INSTALL_PYTHON_DIR"
  rm -rf "$STANDARD_INSTALL_ROOT"
fi

emit_progress 100 "Uninstall completed"
echo "[Done] Uninstall completed."
if [[ "${#WARNINGS[@]}" -gt 0 ]]; then
  echo "[Note] Uninstall completed with warnings:"
  for warning in "${WARNINGS[@]}"; do
    echo "  - $warning"
  done
fi
if [[ "$DELETE_DIR" -eq 0 ]]; then
  echo "[Hint] Add --delete-project-dir to remove the source directory too."
fi
