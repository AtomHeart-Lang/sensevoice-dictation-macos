#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="FunASR Dictation"
APP_VERSION="2.1.9"
INSTALLER_APP_NAME="Install FunASR Dictation.app"
DMG_NAME="funasr-dictation-installer-${APP_VERSION}.dmg"
WORK_DIR="$(mktemp -d /tmp/funasr-dmg.XXXXXX)"
STAGE_DIR="$WORK_DIR/stage"
PAYLOAD_ROOT="$WORK_DIR/payload"
PAYLOAD_APP_DIR="$PAYLOAD_ROOT/sensevoice-dictation-macos"
PAYLOAD_ARCHIVE="$WORK_DIR/funasr-dictation-payload.tar.gz"
INSTALLER_APP="$STAGE_DIR/$INSTALLER_APP_NAME"
ICON_SRC="$APP_DIR/assets/app_launcher_icon.png"
TASK_RUNNER_SRC="$APP_DIR/task_runner/TaskProgressApp.m"
TASK_RUNNER_BIN="$WORK_DIR/TaskProgressApp"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p "$STAGE_DIR" "$PAYLOAD_APP_DIR" "$INSTALLER_APP/Contents/MacOS" "$INSTALLER_APP/Contents/Resources"

echo "[Step] Staging payload"
rsync -a \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  --exclude "*.log" \
  --exclude "*.lock" \
  --exclude "*.zip" \
  --exclude "*.dmg" \
  --exclude "config.toml" \
  --exclude "ui_settings.json" \
  --exclude ".DS_Store" \
  "$APP_DIR/" "$PAYLOAD_APP_DIR/"

chmod +x \
  "$PAYLOAD_APP_DIR/install.sh" \
  "$PAYLOAD_APP_DIR/start_app.sh" \
  "$PAYLOAD_APP_DIR/create_launcher.sh" \
  "$PAYLOAD_APP_DIR/create_desktop_shortcut.sh" \
  "$PAYLOAD_APP_DIR/create_uninstaller.sh" \
  "$PAYLOAD_APP_DIR/launch_from_desktop.sh" \
  "$PAYLOAD_APP_DIR/remove_launcher.sh" \
  "$PAYLOAD_APP_DIR/enable_autostart.sh" \
  "$PAYLOAD_APP_DIR/disable_autostart.sh" \
  "$PAYLOAD_APP_DIR/uninstall.sh" \
  "$PAYLOAD_APP_DIR/install_from_dmg.command" \
  "$PAYLOAD_APP_DIR/download_python_runtime.sh"

echo "[Step] Building bundled launcher binary"
mkdir -p "$PAYLOAD_APP_DIR/launcher"
if ! clang -arch arm64 -arch x86_64 "$APP_DIR/launcher/FunASRLauncher.c" -O2 \
  -framework ApplicationServices \
  -framework CoreFoundation \
  -o "$PAYLOAD_APP_DIR/launcher/FunASRLauncher" >/dev/null 2>&1; then
  clang "$APP_DIR/launcher/FunASRLauncher.c" -O2 \
    -framework ApplicationServices \
    -framework CoreFoundation \
    -o "$PAYLOAD_APP_DIR/launcher/FunASRLauncher"
fi
chmod +x "$PAYLOAD_APP_DIR/launcher/FunASRLauncher"

echo "[Step] Building task progress app"
mkdir -p "$PAYLOAD_APP_DIR/task_runner"
if ! clang -fobjc-arc -arch arm64 -arch x86_64 "$TASK_RUNNER_SRC" -framework Cocoa -o "$TASK_RUNNER_BIN" >/dev/null 2>&1; then
  clang -fobjc-arc "$TASK_RUNNER_SRC" -framework Cocoa -o "$TASK_RUNNER_BIN"
fi
chmod +x "$TASK_RUNNER_BIN"
cp "$TASK_RUNNER_BIN" "$PAYLOAD_APP_DIR/task_runner/TaskProgressApp"

echo "[Step] Packing payload archive"
tar -czf "$PAYLOAD_ARCHIVE" -C "$PAYLOAD_ROOT" "sensevoice-dictation-macos"
cp "$PAYLOAD_ARCHIVE" "$INSTALLER_APP/Contents/Resources/funasr-dictation-payload.tar.gz"
cp "$APP_DIR/install_from_dmg.command" "$INSTALLER_APP/Contents/Resources/run_task.sh"
chmod +x "$INSTALLER_APP/Contents/Resources/run_task.sh"
cp "$TASK_RUNNER_BIN" "$INSTALLER_APP/Contents/MacOS/TaskProgressApp"
chmod +x "$INSTALLER_APP/Contents/MacOS/TaskProgressApp"

cat > "$INSTALLER_APP/Contents/Resources/TaskRunnerConfig.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Mode</key>
  <string>install</string>
  <key>AppDisplayName</key>
  <string>$APP_NAME</string>
  <key>ScriptRelativePath</key>
  <string>run_task.sh</string>
  <key>ConfirmRequired</key>
  <false/>
  <key>ShowSuccessOpenButton</key>
  <true/>
  <key>ShowDesktopShortcutButton</key>
  <true/>
</dict>
</plist>
PLIST

cat > "$INSTALLER_APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Install FunASR Dictation</string>
  <key>CFBundleDisplayName</key>
  <string>Install FunASR Dictation</string>
  <key>CFBundleIdentifier</key>
  <string>com.lee.funasr.dictation.installer</string>
  <key>CFBundleVersion</key>
  <string>$APP_VERSION</string>
  <key>CFBundleShortVersionString</key>
  <string>$APP_VERSION</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>TaskProgressApp</string>
  <key>CFBundleIconFile</key>
  <string>app</string>
  <key>CFBundleIconName</key>
  <string>app</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
</dict>
</plist>
PLIST

cat > "$STAGE_DIR/README.txt" <<TXT
FunASR Dictation macOS Installer

1. Double-click "Install FunASR Dictation.app"
2. A native macOS installer window will show live progress while the standalone Python runtime, Python dependencies, and the latest model are downloaded
3. When installation completes, optionally click "Create Desktop Shortcut" in the installer window
4. Desktop shortcuts may need to be deleted manually during uninstall, depending on macOS permissions
5. Click "Open App" in the installer window
6. Grant Microphone / Accessibility / Input Monitoring when FunASR Dictation first launches

The DMG does not include the model cache.
No Homebrew or preinstalled Python is required on the target Mac.
TXT

if [[ -f "$ICON_SRC" ]]; then
  ICONSET_DIR="$WORK_DIR/icon.iconset"
  ICON_ICNS="$WORK_DIR/app.icns"
  mkdir -p "$ICONSET_DIR"
  if (
    sips -z 16 16     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null &&
    sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null &&
    sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null &&
    sips -z 64 64     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null &&
    sips -z 128 128   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null &&
    sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null &&
    sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null &&
    sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null &&
    sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null &&
    sips -z 1024 1024 "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null &&
    iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS" >/dev/null
  ); then
    cp "$ICON_ICNS" "$INSTALLER_APP/Contents/Resources/app.icns"
  else
    echo "[WARN] Failed to build installer icon. Continuing without custom installer icon."
  fi
fi

codesign --force --deep --sign - "$INSTALLER_APP" >/dev/null 2>&1 || true

echo "[Step] Creating DMG"
rm -f "$APP_DIR/$DMG_NAME"
hdiutil create -volname "$APP_NAME Installer" -srcfolder "$STAGE_DIR" -ov -format UDZO "$APP_DIR/$DMG_NAME" >/dev/null

echo "[OK] DMG created: $APP_DIR/$DMG_NAME"
