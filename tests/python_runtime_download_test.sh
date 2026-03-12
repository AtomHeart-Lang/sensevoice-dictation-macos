#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REPO_DIR/download_python_runtime.sh"

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

assert_contains() {
  local file="$1"
  local text="$2"
  grep -Fq "$text" "$file" || fail "Expected '$text' in $file"
}

run_http2_fallback_test() {
  local tmp_root fakebin install_root log_file output_path expected_bin
  tmp_root="$(mktemp -d /tmp/funasr-python-test.XXXXXX)"
  fakebin="$tmp_root/fakebin"
  install_root="$tmp_root/install-root"
  log_file="$tmp_root/download.log"
  expected_bin="$install_root/python-runtime/python/bin/python3.11"
  trap 'rm -rf "$tmp_root"' RETURN

  mkdir -p "$fakebin"

  cat >"$fakebin/uname" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "-s" ]]; then
  echo "Darwin"
elif [[ "$1" == "-m" ]]; then
  echo "arm64"
else
  /usr/bin/uname "$@"
fi
EOF

  cat >"$fakebin/curl" <<'EOF'
#!/usr/bin/env bash
state_file="${FAKE_CURL_STATE_FILE:?}"
output=""
use_http11=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -o)
      output="$2"
      shift 2
      ;;
    --http1.1)
      use_http11=1
      shift
      ;;
    *)
      shift
      ;;
  esac
done
if [[ "$use_http11" -eq 0 ]]; then
  echo "http2_failed" >"$state_file"
  echo "curl: (16) Error in the HTTP2 framing layer" >&2
  exit 16
fi
echo "http1_success" >"$state_file"
printf 'fake archive' >"$output"
EOF

  cat >"$fakebin/shasum" <<'EOF'
#!/usr/bin/env bash
echo "${FAKE_SHA256:?}  $2"
EOF

  cat >"$fakebin/tar" <<'EOF'
#!/usr/bin/env bash
dest=""
while [[ "$#" -gt 0 ]]; do
  if [[ "$1" == "-C" ]]; then
    dest="$2"
    shift 2
  else
    shift
  fi
done
mkdir -p "$dest/python/bin"
cat >"$dest/python/bin/python3.11" <<'PYEOF'
#!/usr/bin/env bash
echo "Python 3.11.15"
PYEOF
chmod +x "$dest/python/bin/python3.11"
EOF

  chmod +x "$fakebin/uname" "$fakebin/curl" "$fakebin/shasum" "$fakebin/tar"

  set +e
  PATH="$fakebin:/usr/bin:/bin" \
  FAKE_CURL_STATE_FILE="$tmp_root/curl.state" \
  FAKE_SHA256="deadbeef" \
  SVD_INSTALL_ROOT="$install_root" \
  SVD_PYTHON_ARCHIVE="fake-python.tar.gz" \
  SVD_PYTHON_SHA256="deadbeef" \
  SVD_PYTHON_URL="https://example.invalid/fake-python.tar.gz" \
  "$SCRIPT" >"$tmp_root/stdout.log" 2>"$log_file"
  exit_code=$?
  set -e

  [[ "$exit_code" -eq 0 ]] || fail "Expected fallback download to succeed, got exit $exit_code"
  output_path="$(cat "$tmp_root/stdout.log")"
  [[ "$output_path" == "$expected_bin" ]] || fail "Expected python path '$expected_bin', got '$output_path'"
  [[ -x "$expected_bin" ]] || fail "Expected extracted python binary at $expected_bin"
  assert_contains "$log_file" "HTTP/2"
  assert_contains "$log_file" "HTTP/1.1"
}

run_http2_fallback_test

echo "[PASS] python runtime download"
