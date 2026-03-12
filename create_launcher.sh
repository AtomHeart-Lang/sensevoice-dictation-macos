#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="FunASR Dictation"
LEGACY_APP_NAME="SenseVoice Dictation"
APP_VERSION="2.1.9"
APP_BUNDLE="$HOME/Applications/$APP_NAME.app"
DESKTOP_APP="$HOME/Desktop/$APP_NAME.app"
LEGACY_APP_BUNDLE="$HOME/Applications/$LEGACY_APP_NAME.app"
LEGACY_DESKTOP_APP="$HOME/Desktop/$LEGACY_APP_NAME.app"
APP_ICON_PNG="$APP_DIR/assets/app_launcher_icon.png"
MENU_ICON_PNG="$APP_DIR/assets/mic_menu_icon.png"
# Keep legacy bundle id for TCC stability across upgrades/renames.
APP_BUNDLE_ID="com.lee.sensevoice.dictation.launcher"
LEGACY_BUNDLE_IDS=(
  "com.lee.funasr.dictation.launcher"
)
APP_SUPPORT_DIR="$HOME/Library/Application Support/SenseVoiceDictation"
LAUNCHER_IDENTITY_FILE="$APP_SUPPORT_DIR/launcher_identity.sha256"
RUNTIME_PATH_FILE="$APP_SUPPORT_DIR/runtime_app_dir.txt"
FORCE_REBUILD=0
CREATE_DESKTOP_SHORTCUT=0
LAUNCHER_BIN="$APP_BUNDLE/Contents/MacOS/FunASRLauncher"
LAUNCHER_SRC="$APP_DIR/launcher/FunASRLauncher.c"
LAUNCHER_TEMPLATE_BIN="$APP_DIR/launcher/FunASRLauncher"

for arg in "$@"; do
  case "$arg" in
    --force|--force-rebuild) FORCE_REBUILD=1 ;;
    --with-desktop-shortcut) CREATE_DESKTOP_SHORTCUT=1 ;;
    *)
      echo "[ERROR] Unknown argument: $arg"
      echo "Usage: ./create_launcher.sh [--force-rebuild] [--with-desktop-shortcut]"
      exit 1
      ;;
  esac
done

create_desktop_shortcut() {
  mkdir -p "$HOME/Desktop"
  rm -f "$DESKTOP_APP"
  ln -s "$APP_BUNDLE" "$DESKTOP_APP"
  echo "[OK] Desktop shortcut created (symlink): $DESKTOP_APP"
}

reset_tcc_for_bundle() {
  local bundle_id="$1"
  tccutil reset All "$bundle_id" >/dev/null 2>&1 || true
  tccutil reset Accessibility "$bundle_id" >/dev/null 2>&1 || true
  tccutil reset ListenEvent "$bundle_id" >/dev/null 2>&1 || true
}

reset_tcc_for_legacy_bundle_ids() {
  local old_id=""
  for old_id in "${LEGACY_BUNDLE_IDS[@]}"; do
    reset_tcc_for_bundle "$old_id"
  done
}

launcher_hash() {
  local bin_path="$1"
  if [[ ! -f "$bin_path" ]]; then
    return 1
  fi
  shasum -a 256 "$bin_path" | awk '{print $1}'
}

launcher_supports_runtime_path() {
  local bin_path="$1"
  [[ -x "$bin_path" ]] || return 1
  strings "$bin_path" 2>/dev/null | grep -q "runtime_path_v2"
}

write_runtime_path_file() {
  mkdir -p "$APP_SUPPORT_DIR"
  printf '%s\n' "$APP_DIR" > "$RUNTIME_PATH_FILE"
}

TMP_DIR="$(mktemp -d /tmp/funasr-launcher.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$HOME/Applications"

# Keep launcher binary stable by default: rebuilding changes ad-hoc cdhash and
# may invalidate previously granted TCC permissions. Rebuild only when forced.
if [[ "$FORCE_REBUILD" -eq 0 && -d "$APP_BUNDLE" && -x "$LAUNCHER_BIN" ]]; then
  rm -rf "$LEGACY_APP_BUNDLE" "$LEGACY_DESKTOP_APP"
  LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
  if [[ -x "$LSREGISTER" ]]; then
    "$LSREGISTER" -f "$APP_BUNDLE" >/dev/null 2>&1 || true
  fi
  mkdir -p "$APP_SUPPORT_DIR"
  if launcher_supports_runtime_path "$LAUNCHER_BIN"; then
    write_runtime_path_file
  fi
  current_hash="$(launcher_hash "$LAUNCHER_BIN" || true)"
  saved_hash="$(cat "$LAUNCHER_IDENTITY_FILE" 2>/dev/null || true)"
  if [[ -n "$current_hash" && "$current_hash" != "$saved_hash" ]]; then
    reset_tcc_for_bundle "$APP_BUNDLE_ID"
    echo "$current_hash" > "$LAUNCHER_IDENTITY_FILE"
    echo "[INFO] Launcher identity changed/migrated. Reset TCC for $APP_BUNDLE_ID once."
  fi
  reset_tcc_for_legacy_bundle_ids
  echo "[OK] Launcher app already exists; skipped rebuild to preserve TCC identity."
  if [[ "$CREATE_DESKTOP_SHORTCUT" -eq 1 ]]; then
    create_desktop_shortcut
  fi
  exit 0
fi

rm -rf "$APP_BUNDLE" "$LEGACY_APP_BUNDLE" "$LEGACY_DESKTOP_APP"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"

cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>FunASR Dictation</string>
  <key>CFBundleDisplayName</key>
  <string>FunASR Dictation</string>
  <key>CFBundleIdentifier</key>
  <string>$APP_BUNDLE_ID</string>
  <key>CFBundleVersion</key>
  <string>$APP_VERSION</string>
  <key>CFBundleShortVersionString</key>
  <string>$APP_VERSION</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSUIElement</key>
  <true/>
  <key>CFBundleExecutable</key>
  <string>FunASRLauncher</string>
  <key>CFBundleIconFile</key>
  <string>app</string>
  <key>CFBundleIconName</key>
  <string>app</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSMicrophoneUsageDescription</key>
  <string>FunASR Dictation needs microphone access to transcribe your speech locally.</string>
</dict>
</plist>
PLIST

if [[ -x "$LAUNCHER_TEMPLATE_BIN" ]]; then
  cp "$LAUNCHER_TEMPLATE_BIN" "$APP_BUNDLE/Contents/MacOS/FunASRLauncher"
  chmod +x "$APP_BUNDLE/Contents/MacOS/FunASRLauncher"
elif command -v clang >/dev/null 2>&1 && [[ -f "$LAUNCHER_SRC" ]]; then
  clang "$LAUNCHER_SRC" -O2 \
    -framework ApplicationServices \
    -framework CoreFoundation \
    -o "$APP_BUNDLE/Contents/MacOS/FunASRLauncher"
else
  echo "[ERROR] No bundled launcher binary found and clang is unavailable."
  echo "Install Xcode Command Line Tools first: xcode-select --install"
  exit 1
fi

ICON_SRC="$APP_ICON_PNG"
if [[ ! -f "$ICON_SRC" ]]; then
  ICON_SRC="$MENU_ICON_PNG"
fi

if [[ -f "$ICON_SRC" ]]; then
  ICONSET_DIR="$TMP_DIR/mic.iconset"
  ICON_ICNS="$TMP_DIR/app.icns"
  mkdir -p "$ICONSET_DIR"
  sips -z 16 16     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
  sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
  sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
  sips -z 64 64     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
  sips -z 128 128   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
  sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
  sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
  sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
  sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
  iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"
  cp "$ICON_ICNS" "$APP_BUNDLE/Contents/Resources/app.icns"
fi

codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true

# Register app with LaunchServices to make `open -a "FunASR Dictation"`
# and `tccutil reset ... <bundle-id>` available immediately after creation.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "$LSREGISTER" ]]; then
  "$LSREGISTER" -f "$APP_BUNDLE" >/dev/null 2>&1 || true
fi

mkdir -p "$APP_SUPPORT_DIR"
write_runtime_path_file
current_hash="$(launcher_hash "$LAUNCHER_BIN" || true)"
if [[ -n "$current_hash" ]]; then
  echo "$current_hash" > "$LAUNCHER_IDENTITY_FILE"
fi
reset_tcc_for_bundle "$APP_BUNDLE_ID"
reset_tcc_for_legacy_bundle_ids

echo "[OK] Launcher app created: $APP_BUNDLE"
if [[ "$CREATE_DESKTOP_SHORTCUT" -eq 1 ]]; then
  create_desktop_shortcut
fi
