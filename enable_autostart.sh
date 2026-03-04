#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.lee.sensevoice.menubar.plist"
LABEL="com.lee.sensevoice.menubar"
DOMAIN="gui/$(id -u)"
AUTOSTART_DIR="$HOME/Library/Application Support/SenseVoiceDictation"
AUTOSTART_RUNNER="$AUTOSTART_DIR/autostart_runner.sh"
AUTOSTART_LOG_DIR="$HOME/Library/Logs/SenseVoiceDictation"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$AUTOSTART_DIR"
mkdir -p "$AUTOSTART_LOG_DIR"

cat > "$AUTOSTART_RUNNER" <<'RUNNER'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="__APP_DIR__"
START_SCRIPT="$APP_DIR/start_app.sh"
LAUNCHER_APP="$HOME/Applications/SenseVoice Dictation.app"
RUNTIME_LOG="$HOME/Library/Logs/SenseVoiceDictation/menubar_runtime.log"
WAIT_LOG="$HOME/Library/Logs/SenseVoiceDictation/autostart_wait.log"

wait_round=0
while [[ ! -d "$APP_DIR" || ! -x "$START_SCRIPT" ]]; do
  wait_round=$((wait_round + 1))
  if (( wait_round % 15 == 0 )); then
    echo "[$(date '+%F %T')] waiting for app dir: $APP_DIR" >> "$WAIT_LOG"
  fi
  sleep 2
done

if pgrep -f "[m]enubar_dictation_app.py" >/dev/null 2>&1; then
  exit 0
fi

if [[ -x "$START_SCRIPT" ]]; then
  cd "$APP_DIR"
  exec /bin/bash "$START_SCRIPT" >>"$RUNTIME_LOG" 2>&1
fi

if [[ -d "$LAUNCHER_APP" ]]; then
  exec /usr/bin/open -gj "$LAUNCHER_APP" >>"$RUNTIME_LOG" 2>&1
fi

echo "[$(date '+%F %T')] autostart failed: launcher/start script not found" >> "$RUNTIME_LOG"
exit 1
RUNNER

sed -i '' "s|__APP_DIR__|$APP_DIR|g" "$AUTOSTART_RUNNER"
chmod +x "$AUTOSTART_RUNNER"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>$AUTOSTART_RUNNER</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$AUTOSTART_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
      <key>SuccessfulExit</key>
      <false/>
    </dict>

    <key>LimitLoadToSessionType</key>
    <array>
      <string>Aqua</string>
    </array>

    <key>StandardOutPath</key>
    <string>$AUTOSTART_LOG_DIR/launchagent.out.log</string>

    <key>StandardErrorPath</key>
    <string>$AUTOSTART_LOG_DIR/launchagent.err.log</string>
  </dict>
</plist>
PLIST

launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
launchctl enable "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true

echo "[OK] Autostart enabled: $PLIST"
echo "[OK] Autostart runner: $AUTOSTART_RUNNER"
