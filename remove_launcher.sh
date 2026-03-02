#!/usr/bin/env bash
set -euo pipefail

APP_BUNDLE="$HOME/Applications/SenseVoice Dictation.app"
DESKTOP_APP="$HOME/Desktop/SenseVoice Dictation.app"

rm -rf "$APP_BUNDLE"
rm -rf "$DESKTOP_APP"

echo "[OK] Launcher app removed"
