#!/usr/bin/env bash
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.lee.sensevoice.menubar.plist"

if [[ -f "$PLIST" ]]; then
  launchctl unload "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  echo "[OK] Autostart disabled: $PLIST"
else
  echo "[INFO] Autostart plist not found"
fi
