#!/usr/bin/env bash
set -euo pipefail

APP_BUNDLE="$HOME/Applications/FunASR Dictation.app"
DESKTOP_APP="$HOME/Desktop/FunASR Dictation.app"
LEGACY_APP_BUNDLE="$HOME/Applications/SenseVoice Dictation.app"
LEGACY_DESKTOP_APP="$HOME/Desktop/SenseVoice Dictation.app"

rm -rf "$APP_BUNDLE"
rm -rf "$DESKTOP_APP"
rm -rf "$LEGACY_APP_BUNDLE"
rm -rf "$LEGACY_DESKTOP_APP"

echo "[OK] Launcher app removed"
