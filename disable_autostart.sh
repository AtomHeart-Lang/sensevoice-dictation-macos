#!/usr/bin/env bash
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.lee.sensevoice.menubar.plist"
LABEL="com.lee.sensevoice.menubar"
DOMAIN="gui/$(id -u)"
AUTOSTART_DIR="$HOME/Library/Application Support/SenseVoiceDictation"
AUTOSTART_RUNNER="$AUTOSTART_DIR/autostart_runner.sh"
AUTOSTART_LOG_DIR="$HOME/Library/Logs/SenseVoiceDictation"

launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
launchctl disable "$DOMAIN/$LABEL" >/dev/null 2>&1 || true

rm -f "$PLIST"
rm -f "$AUTOSTART_RUNNER"
rmdir "$AUTOSTART_DIR" >/dev/null 2>&1 || true
rm -f "$AUTOSTART_LOG_DIR"/launchagent.out.log "$AUTOSTART_LOG_DIR"/launchagent.err.log "$AUTOSTART_LOG_DIR"/autostart_wait.log
rmdir "$AUTOSTART_LOG_DIR" >/dev/null 2>&1 || true

echo "[OK] Autostart disabled."
