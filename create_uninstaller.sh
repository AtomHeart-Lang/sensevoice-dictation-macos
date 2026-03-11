#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Uninstall FunASR Dictation"
APP_VERSION="2.0.2"
APP_BUNDLE="$HOME/Applications/$APP_NAME.app"
APP_SUPPORT_DIR="$HOME/Library/Application Support/SenseVoiceDictation"
RUNTIME_PATH_FILE="$APP_SUPPORT_DIR/runtime_app_dir.txt"
ICON_SRC="$(cd "$(dirname "$0")" && pwd)/assets/app_launcher_icon.png"
TMP_DIR="$(mktemp -d /tmp/funasr-uninstaller.XXXXXX)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$HOME/Applications"
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"

cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>com.lee.funasr.dictation.uninstaller</string>
  <key>CFBundleVersion</key>
  <string>$APP_VERSION</string>
  <key>CFBundleShortVersionString</key>
  <string>$APP_VERSION</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>FunASRUninstaller</string>
  <key>CFBundleIconFile</key>
  <string>app</string>
  <key>CFBundleIconName</key>
  <string>app</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
</dict>
</plist>
PLIST

cat > "$APP_BUNDLE/Contents/MacOS/FunASRUninstaller" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

APP_SUPPORT_DIR="$HOME/Library/Application Support/SenseVoiceDictation"
RUNTIME_PATH_FILE="$APP_SUPPORT_DIR/runtime_app_dir.txt"
STANDARD_RUNTIME_DIR="$HOME/Library/Application Support/FunASRDictation/app"

runtime_dir="$(cat "$RUNTIME_PATH_FILE" 2>/dev/null || true)"
runtime_dir="${runtime_dir%$'\r'}"

if [[ -z "$runtime_dir" || ! -d "$runtime_dir" || ! -x "$runtime_dir/uninstall.sh" ]]; then
  osascript -e 'display alert "FunASR Dictation" message "Installed runtime was not found. Please remove the app manually if it is already gone." as critical'
  exit 1
fi

confirm=$(
  osascript <<OSA
button returned of (display dialog "This will remove FunASR Dictation, its launcher, Python runtime, model cache, and local settings." buttons {"Cancel", "Uninstall"} default button "Uninstall" with icon caution)
OSA
) || exit 0

if [[ "$confirm" != "Uninstall" ]]; then
  exit 0
fi

tmp_script="$(mktemp /tmp/funasr-uninstall-run.XXXXXX.sh)"
chmod 700 "$tmp_script"

if [[ "$runtime_dir" == "$STANDARD_RUNTIME_DIR" ]]; then
  uninstall_args="--delete-project-dir"
else
  uninstall_args=""
fi

cat > "$tmp_script" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$runtime_dir"
./uninstall.sh $uninstall_args
rm -f "$tmp_script"
EOF

if open -b com.apple.Terminal "$tmp_script" >/dev/null 2>&1; then
  exit 0
fi

osascript <<OSA
tell application id "com.apple.Terminal"
  activate
  do script quoted form of "$tmp_script"
end tell
OSA
SCRIPT
chmod +x "$APP_BUNDLE/Contents/MacOS/FunASRUninstaller"

if [[ -f "$ICON_SRC" ]]; then
  ICONSET_DIR="$TMP_DIR/app.iconset"
  ICON_ICNS="$TMP_DIR/app.icns"
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
    cp "$ICON_ICNS" "$APP_BUNDLE/Contents/Resources/app.icns"
  fi
fi

codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true

echo "[OK] Uninstaller app created: $APP_BUNDLE"
