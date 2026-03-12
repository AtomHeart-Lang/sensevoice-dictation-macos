#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_ROOT="$HOME/Library/Application Support/FunASRDictation"
APP_DIR="$INSTALL_ROOT/app"
PAYLOAD_ARCHIVE="$SCRIPT_DIR/funasr-dictation-payload.tar.gz"
BACKUP_DIR=""
RESTORE_ON_ERROR=1
LOG_FILE="$INSTALL_ROOT/install.log"

emit_progress() {
  local percent="$1"
  shift
  echo "[Progress] $percent $*"
}

mkdir -p "$INSTALL_ROOT"
TMP_DIR="$(mktemp -d "$INSTALL_ROOT/.payload.XXXXXX")"
exec > >(tee -a "$LOG_FILE") 2>&1

cleanup() {
  rm -rf "$TMP_DIR"
  if [[ "$RESTORE_ON_ERROR" -eq 1 ]]; then
    if [[ -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]]; then
      rm -rf "$APP_DIR"
      mv "$BACKUP_DIR" "$APP_DIR"
      echo "[WARN] Installation failed. Restored previous installation."
    else
      rm -rf "$APP_DIR"
    fi
  elif [[ -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]]; then
    rm -rf "$BACKUP_DIR"
  fi
}
trap cleanup EXIT

on_error() {
  local exit_code="$1"
  local line_no="$2"
  echo
  echo "[ERROR] DMG installation failed at line $line_no (exit $exit_code)."
  echo "[ERROR] Check log: $LOG_FILE"
  if [[ "${FUNASR_UI_MODE:-0}" != "1" ]]; then
    osascript <<OSA >/dev/null 2>&1 || true
display alert "FunASR Dictation Installer" message "Installation failed. Check log:\n$LOG_FILE" as critical
OSA
  fi
}
trap 'on_error $? $LINENO' ERR

if [[ ! -f "$PAYLOAD_ARCHIVE" ]]; then
  echo "[ERROR] Missing installer payload: $PAYLOAD_ARCHIVE"
  exit 1
fi

emit_progress 6 "Preparing installation"
echo "[Step] Stopping running app instance"
pkill -f "[m]enubar_dictation_app.py" >/dev/null 2>&1 || true
pkill -f "[s]tart_app.sh" >/dev/null 2>&1 || true

emit_progress 12 "Extracting installer payload"
echo "[Step] Extracting payload"
tar -xzf "$PAYLOAD_ARCHIVE" -C "$TMP_DIR"

PAYLOAD_APP_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$PAYLOAD_APP_DIR" || ! -d "$PAYLOAD_APP_DIR" ]]; then
  echo "[ERROR] Invalid payload layout."
  exit 1
fi

if [[ -d "$APP_DIR" ]]; then
  BACKUP_DIR="$INSTALL_ROOT/app.backup.$(date +%s)"
  mv "$APP_DIR" "$BACKUP_DIR"
fi

mv "$PAYLOAD_APP_DIR" "$APP_DIR"

if [[ -n "$BACKUP_DIR" && -f "$BACKUP_DIR/config.toml" && ! -f "$APP_DIR/config.toml" ]]; then
  cp "$BACKUP_DIR/config.toml" "$APP_DIR/config.toml"
fi

cd "$APP_DIR"

emit_progress 20 "Installing runtime and dependencies"
echo "[Step] Installing runtime and downloading latest model"
STANDALONE_PYTHON="$(./download_python_runtime.sh)"
SVD_PYTHON_BIN="$STANDALONE_PYTHON" ./install.sh --no-launcher

emit_progress 95 "Creating launcher app"
echo "[Step] Rebuilding launcher for installed runtime path"
./create_launcher.sh --force-rebuild

RESTORE_ON_ERROR=0

echo
emit_progress 100 "Installation completed"
echo "[Done] Installation completed."
echo "[Note] App: $HOME/Applications/FunASR Dictation.app"
echo "[Note] Desktop shortcut is optional and is no longer created by default."
echo "[Note] Use the installer window if you want to create a Desktop shortcut."
echo "[Note] If created, macOS may require deleting the Desktop shortcut manually during uninstall."
echo "[Note] Open FunASR Dictation from the installer window or from ~/Applications after this window closes."
echo "[Note] On first launch, grant Microphone, Accessibility, and Input Monitoring to FunASR Dictation."
echo "[Note] Models are downloaded during installation and are not bundled in the DMG."
