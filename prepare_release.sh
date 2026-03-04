#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

rm -rf __pycache__
find . -name "*.pyc" -delete
rm -f .DS_Store assets/.DS_Store
rm -f menubar_debug.log menubar_runtime.log menubar.out.log menubar.err.log
rm -f menubar_app.lock
# Keep local runtime configs; release zip already excludes them.

ZIP_NAME="sensevoice-dictation-macos-release.zip"
rm -f "$ZIP_NAME"
zip -r "$ZIP_NAME" . \
  -x ".venv/*" \
  -x ".git/*" \
  -x "*.log" \
  -x "*.lock" \
  -x "__pycache__/*" \
  -x "config.toml" \
  -x "ui_settings.json"

echo "[OK] Cleaned local artifacts."
echo "[OK] Release zip: $APP_DIR/$ZIP_NAME"
