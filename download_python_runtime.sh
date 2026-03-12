#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${SVD_INSTALL_ROOT:-$HOME/Library/Application Support/FunASRDictation}"
RUNTIME_ROOT="$INSTALL_ROOT/python-runtime"
PYTHON_DIR="$RUNTIME_ROOT/python"
PYTHON_BIN="$PYTHON_DIR/bin/python3.11"
RELEASE_TAG="20260303"
VERSION="3.11.15+20260303"
PYTHON_ARCHIVE=""
PYTHON_SHA256=""
PYTHON_URL=""

is_chinese_locale() {
  local locale="${LC_ALL:-${LC_MESSAGES:-${LANG:-${AppleLocale:-}}}}"
  locale="$(printf '%s' "$locale" | tr '[:upper:]' '[:lower:]')"
  [[ "$locale" == zh* ]]
}

localize() {
  local zh="$1"
  local en="$2"
  if is_chinese_locale; then
    printf '%s\n' "$zh"
  else
    printf '%s\n' "$en"
  fi
}

emit_progress() {
  local percent="$1"
  shift
  echo "[Progress] $percent $*" >&2
}

pick_asset() {
  local arch
  arch="$(uname -m)"
  case "$arch" in
    arm64|aarch64)
      PYTHON_ARCHIVE="cpython-${VERSION}-aarch64-apple-darwin-install_only_stripped.tar.gz"
      PYTHON_SHA256="3ac3262428d899422dcf07ec0c69f8c99abc78ba36b497ffcb0f981d28ae0136"
      ;;
    x86_64)
      PYTHON_ARCHIVE="cpython-${VERSION}-x86_64-apple-darwin-install_only_stripped.tar.gz"
      PYTHON_SHA256="9038d161defcbedc0b723fa48f60890057d18a89167609d594299432f2e059f1"
      ;;
    *)
      echo "[ERROR] $(localize "不支持的 macOS 架构：$arch" "Unsupported macOS architecture: $arch")"
      exit 1
      ;;
  esac
  PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${RELEASE_TAG}/${PYTHON_ARCHIVE//+/%%2B}"
  PYTHON_URL="${PYTHON_URL//%%2B/%2B}"

  if [[ -n "${SVD_PYTHON_ARCHIVE:-}" ]]; then
    PYTHON_ARCHIVE="$SVD_PYTHON_ARCHIVE"
  fi
  if [[ -n "${SVD_PYTHON_SHA256:-}" ]]; then
    PYTHON_SHA256="$SVD_PYTHON_SHA256"
  fi
  if [[ -n "${SVD_PYTHON_URL:-}" ]]; then
    PYTHON_URL="$SVD_PYTHON_URL"
  fi
}

curl_attempt() {
  local mode_label="$1"
  shift
  local extra_args=("$@")
  local attempt exit_code

  for attempt in 1 2 3; do
    local curl_cmd=(
      curl --fail --location --progress-bar
      --connect-timeout 20
      --retry 2
      --retry-delay 1
      --retry-all-errors
    )
    if [[ "${#extra_args[@]}" -gt 0 ]]; then
      curl_cmd+=("${extra_args[@]}")
    fi
    curl_cmd+=("$PYTHON_URL" -o "$ARCHIVE_PATH")
    if "${curl_cmd[@]}"; then
      return 0
    else
      exit_code=$?
    fi
    echo "[WARN] $(localize "独立 Python 下载失败（${mode_label}，第 ${attempt} 次尝试，退出码 ${exit_code}）。" "Standalone Python download failed (${mode_label}, attempt ${attempt}, exit ${exit_code}).")" >&2
    if [[ "$attempt" -lt 3 ]]; then
      sleep 1
    fi
  done

  return "$exit_code"
}

download_python_archive() {
  local exit_code=0
  if curl_attempt "HTTP/2"; then
    return 0
  else
    exit_code=$?
  fi

  if [[ "$exit_code" -eq 16 || "$exit_code" -eq 18 || "$exit_code" -eq 28 || "$exit_code" -eq 56 || "$exit_code" -eq 92 ]]; then
    echo "[WARN] $(localize "检测到 HTTP/2 下载不稳定，正在回退到 HTTP/1.1 重试。" "Detected unstable HTTP/2 download, falling back to HTTP/1.1.")" >&2
    emit_progress 28 "$(localize "HTTP/2 失败，回退到 HTTP/1.1 重试" "HTTP/2 failed, retrying with HTTP/1.1")"
    echo "[Step] $(localize "使用 HTTP/1.1 重试下载" "Retrying download with HTTP/1.1")" >&2
    curl_attempt "HTTP/1.1" --http1.1
    return $?
  fi

  return "$exit_code"
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[ERROR] $(localize "此脚本仅支持 macOS。" "This script only supports macOS.")"
  exit 1
fi

pick_asset

if [[ -x "$PYTHON_BIN" ]]; then
  if "$PYTHON_BIN" -V >/dev/null 2>&1; then
    emit_progress 32 "$(localize "使用现有独立 Python 运行时" "Using existing standalone Python runtime")"
    echo "[OK] $(localize "独立 Python 已可用：$PYTHON_BIN" "Standalone Python already available: $PYTHON_BIN")" >&2
    echo "$PYTHON_BIN"
    exit 0
  fi
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[ERROR] $(localize "下载独立 Python 运行时需要 curl。" "curl is required to download the standalone Python runtime.")"
  exit 1
fi

TMP_DIR="$(mktemp -d /tmp/funasr-python-runtime.XXXXXX)"
ARCHIVE_PATH="$TMP_DIR/$PYTHON_ARCHIVE"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$INSTALL_ROOT"

emit_progress 24 "$(localize "下载独立 Python 运行时" "Downloading standalone Python runtime")"
echo "[Step] $(localize "下载独立 Python 运行时" "Downloading standalone Python runtime")" >&2
download_python_archive

actual_sha="$(shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}')"
if [[ "$actual_sha" != "$PYTHON_SHA256" ]]; then
  echo "[ERROR] $(localize "独立 Python 校验和不匹配。" "Standalone Python checksum mismatch.")" >&2
  echo "Expected: $PYTHON_SHA256" >&2
  echo "Actual:   $actual_sha" >&2
  exit 1
fi

emit_progress 32 "$(localize "解压独立 Python 运行时" "Extracting standalone Python runtime")"
echo "[Step] $(localize "解压独立 Python 运行时" "Extracting standalone Python runtime")" >&2
rm -rf "$RUNTIME_ROOT"
mkdir -p "$RUNTIME_ROOT"
tar -xzf "$ARCHIVE_PATH" -C "$RUNTIME_ROOT"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] $(localize "独立 Python 已解压，但未找到可执行文件：$PYTHON_BIN" "Standalone Python extracted, but executable not found: $PYTHON_BIN")" >&2
  exit 1
fi

emit_progress 36 "$(localize "独立 Python 运行时已就绪" "Standalone Python runtime is ready")"
echo "[OK] $(localize "独立 Python 已就绪：$PYTHON_BIN" "Standalone Python ready: $PYTHON_BIN")" >&2
echo "$PYTHON_BIN"
