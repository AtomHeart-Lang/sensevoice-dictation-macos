#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="FunASR Dictation"
LEGACY_APP_NAME="SenseVoice Dictation"
APP_BUNDLE="$HOME/Applications/$APP_NAME.app"
DESKTOP_APP="$HOME/Desktop/$APP_NAME.app"
LEGACY_APP_BUNDLE="$HOME/Applications/$LEGACY_APP_NAME.app"
LEGACY_DESKTOP_APP="$HOME/Desktop/$LEGACY_APP_NAME.app"
APP_ICON_PNG="$APP_DIR/assets/app_launcher_icon.png"
MENU_ICON_PNG="$APP_DIR/assets/mic_menu_icon.png"
APP_BUNDLE_ID="com.lee.funasr.dictation.launcher"

if ! command -v clang >/dev/null 2>&1; then
  echo "[ERROR] clang not found. Install Xcode Command Line Tools first: xcode-select --install"
  exit 1
fi

TMP_DIR="$(mktemp -d /tmp/funasr-launcher.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$HOME/Applications"
rm -rf "$APP_BUNDLE" "$DESKTOP_APP" "$LEGACY_APP_BUNDLE" "$LEGACY_DESKTOP_APP"
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
  <string>1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
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

LAUNCH_SRC="$TMP_DIR/launcher_main.m"
cat > "$LAUNCH_SRC" <<SRC
#include <stdlib.h>
#include <ApplicationServices/ApplicationServices.h>
#include <CoreFoundation/CoreFoundation.h>
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#include <dispatch/dispatch.h>

static void request_tcc_permissions(void) {
    // Input Monitoring prompt (ListenEvent).
    CGRequestListenEventAccess();
    // Accessibility prompt.
    const void *keys[] = { kAXTrustedCheckOptionPrompt };
    const void *vals[] = { kCFBooleanTrue };
    CFDictionaryRef options = CFDictionaryCreate(
        kCFAllocatorDefault,
        keys,
        vals,
        1,
        &kCFCopyStringDictionaryKeyCallBacks,
        &kCFTypeDictionaryValueCallBacks
    );
    if (options != NULL) {
        AXIsProcessTrustedWithOptions(options);
        CFRelease(options);
    }

    // Microphone prompt.
    @autoreleasepool {
        AVAuthorizationStatus status = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio];
        if (status == AVAuthorizationStatusNotDetermined) {
            dispatch_semaphore_t sema = dispatch_semaphore_create(0);
            [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio
                                     completionHandler:^(BOOL granted) {
                                         (void)granted;
                                         dispatch_semaphore_signal(sema);
                                     }];
            // Wait for user's first response once so permission state is settled
            // before Python audio stream starts.
            dispatch_time_t timeout = dispatch_time(DISPATCH_TIME_NOW, (int64_t)(120 * NSEC_PER_SEC));
            dispatch_semaphore_wait(sema, timeout);
        }
    }
}

int main(void) {
    request_tcc_permissions();
    return system("cd '$APP_DIR' && ./launch_from_desktop.sh >/dev/null 2>&1");
}
SRC
clang "$LAUNCH_SRC" -O2 \
  -fobjc-arc \
  -fblocks \
  -framework ApplicationServices \
  -framework CoreFoundation \
  -framework Foundation \
  -framework AVFoundation \
  -o "$APP_BUNDLE/Contents/MacOS/FunASRLauncher"

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

ln -s "$APP_BUNDLE" "$DESKTOP_APP"

echo "[OK] Launcher app created: $APP_BUNDLE"
echo "[OK] Desktop shortcut created (symlink): $DESKTOP_APP"
