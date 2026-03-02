#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec ./disable_autostart.sh "$@"
