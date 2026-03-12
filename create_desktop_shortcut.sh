#!/usr/bin/env bash
set -euo pipefail

APP_NAME="FunASR Dictation"
APP_BUNDLE="$HOME/Applications/$APP_NAME.app"
DESKTOP_APP="$HOME/Desktop/$APP_NAME.app"

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "[ERROR] Launcher app not found: $APP_BUNDLE"
  echo "Run ./create_launcher.sh first."
  exit 1
fi

mkdir -p "$HOME/Desktop"
rm -f "$DESKTOP_APP"
ln -s "$APP_BUNDLE" "$DESKTOP_APP"

echo "[OK] Desktop shortcut created (symlink): $DESKTOP_APP"
echo "[WARN] macOS may require deleting the Desktop shortcut manually during uninstall."
