#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BUNDLE="$HOME/Applications/SenseVoice Dictation.app"
DESKTOP_APP="$HOME/Desktop/SenseVoice Dictation.app"
ICON_PNG="$APP_DIR/assets/mic_menu_icon.png"

if ! command -v clang >/dev/null 2>&1; then
  echo "[ERROR] clang not found. Install Xcode Command Line Tools first: xcode-select --install"
  exit 1
fi

TMP_DIR="$(mktemp -d /tmp/sv-launcher.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$HOME/Applications"
rm -rf "$APP_BUNDLE" "$DESKTOP_APP"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"

cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>SenseVoice Dictation</string>
  <key>CFBundleDisplayName</key>
  <string>SenseVoice Dictation</string>
  <key>CFBundleIdentifier</key>
  <string>com.lee.sensevoice.dictation.launcher</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>SenseVoiceLauncher</string>
  <key>CFBundleIconFile</key>
  <string>app</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
</dict>
</plist>
PLIST

LAUNCH_SRC="$TMP_DIR/launcher_main.c"
cat > "$LAUNCH_SRC" <<SRC
#include <stdlib.h>
int main(void) {
    return system("cd '$APP_DIR' && nohup ./start_app.sh >'$APP_DIR/menubar_runtime.log' 2>&1 &");
}
SRC
clang "$LAUNCH_SRC" -O2 -o "$APP_BUNDLE/Contents/MacOS/SenseVoiceLauncher"

if [[ -f "$ICON_PNG" ]]; then
  ICONSET_DIR="$TMP_DIR/mic.iconset"
  ICON_ICNS="$TMP_DIR/app.icns"
  mkdir -p "$ICONSET_DIR"
  sips -z 16 16     "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
  sips -z 32 32     "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
  sips -z 32 32     "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
  sips -z 64 64     "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
  sips -z 128 128   "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
  sips -z 256 256   "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
  sips -z 256 256   "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
  sips -z 512 512   "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
  sips -z 512 512   "$ICON_PNG" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "$ICON_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
  iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"
  cp "$ICON_ICNS" "$APP_BUNDLE/Contents/Resources/app.icns"
fi

codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true
cp -R "$APP_BUNDLE" "$DESKTOP_APP"

echo "[OK] Launcher app created: $APP_BUNDLE"
echo "[OK] Desktop shortcut created: $DESKTOP_APP"
