#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CREATE_LAUNCHER="$REPO_DIR/create_launcher.sh"
UNINSTALL_SCRIPT="$REPO_DIR/uninstall.sh"

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

assert_file_exists() {
  local path="$1"
  [[ -e "$path" ]] || fail "Expected path to exist: $path"
}

assert_not_exists() {
  local path="$1"
  [[ ! -e "$path" ]] || fail "Expected path to be absent: $path"
}

assert_contains() {
  local file="$1"
  local text="$2"
  grep -Fq "$text" "$file" || fail "Expected '$text' in $file"
}

run_create_launcher_default_test() {
  local tmp_home fakebin
  tmp_home="$(mktemp -d /tmp/funasr-test-home.XXXXXX)"
  fakebin="$tmp_home/fakebin"
  trap 'rm -rf "$tmp_home"' RETURN

  mkdir -p "$tmp_home/Desktop" "$fakebin"
  cat >"$fakebin/iconutil" <<'EOF'
#!/usr/bin/env bash
out=""
while [[ "$#" -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then
    out="$2"
    shift 2
  else
    shift
  fi
done
[[ -n "$out" ]] && : >"$out"
EOF
  chmod +x "$fakebin/iconutil"
  HOME="$tmp_home" PATH="$fakebin:$PATH" "$CREATE_LAUNCHER" --force-rebuild >/tmp/funasr-create-launcher.log 2>&1

  assert_file_exists "$tmp_home/Applications/FunASR Dictation.app"
  assert_not_exists "$tmp_home/Desktop/FunASR Dictation.app"
}

run_create_desktop_shortcut_opt_in_test() {
  local tmp_home fakebin
  tmp_home="$(mktemp -d /tmp/funasr-test-home.XXXXXX)"
  fakebin="$tmp_home/fakebin"
  trap 'rm -rf "$tmp_home"' RETURN

  mkdir -p "$tmp_home/Desktop" "$fakebin"
  cat >"$fakebin/iconutil" <<'EOF'
#!/usr/bin/env bash
out=""
while [[ "$#" -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then
    out="$2"
    shift 2
  else
    shift
  fi
done
[[ -n "$out" ]] && : >"$out"
EOF
  chmod +x "$fakebin/iconutil"
  HOME="$tmp_home" PATH="$fakebin:$PATH" "$CREATE_LAUNCHER" --force-rebuild --with-desktop-shortcut >/tmp/funasr-create-shortcut.log 2>&1

  assert_file_exists "$tmp_home/Applications/FunASR Dictation.app"
  assert_file_exists "$tmp_home/Desktop/FunASR Dictation.app"
}

run_uninstall_warning_test() {
  local tmp_home tmp_app log_file exit_code
  tmp_home="$(mktemp -d /tmp/funasr-test-home.XXXXXX)"
  tmp_app="$(mktemp -d /tmp/funasr-test-app.XXXXXX)"
  trap 'chmod 755 "$tmp_home/Desktop" >/dev/null 2>&1 || true; rm -rf "$tmp_home" "$tmp_app"' RETURN

  mkdir -p \
    "$tmp_home/Applications" \
    "$tmp_home/Desktop" \
    "$tmp_home/Library/Application Support/FunASRDictation" \
    "$tmp_home/Library/Application Support/SenseVoiceDictation" \
    "$tmp_home/Library/LaunchAgents" \
    "$tmp_home/.cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512"
  mkdir -p "$tmp_app/.venv" "$tmp_app/__pycache__"
  touch "$tmp_app/config.toml" "$tmp_app/menubar_debug.log"
  ln -s "$tmp_home/Applications/FunASR Dictation.app" "$tmp_home/Desktop/FunASR Dictation.app"
  mkdir -p "$tmp_home/Applications/FunASR Dictation.app"
  mkdir -p "$tmp_home/Applications/Uninstall FunASR Dictation.app"

  cp "$UNINSTALL_SCRIPT" "$tmp_app/uninstall.sh"
  chmod +x "$tmp_app/uninstall.sh"
  chmod 555 "$tmp_home/Desktop"

  log_file="$tmp_home/uninstall.log"
  set +e
  HOME="$tmp_home" "$tmp_app/uninstall.sh" >"$log_file" 2>&1
  exit_code=$?
  set -e

  [[ "$exit_code" -eq 0 ]] || fail "Expected uninstall to succeed, got exit $exit_code"
  assert_contains "$log_file" "[WARN] Desktop shortcut could not be removed automatically"
  assert_contains "$log_file" "Please delete it manually from Desktop."
  assert_contains "$log_file" "[Done] Uninstall completed."
}

run_create_launcher_default_test
run_create_desktop_shortcut_opt_in_test
run_uninstall_warning_test

echo "[PASS] desktop shortcut flow"
