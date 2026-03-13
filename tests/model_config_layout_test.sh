#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

python3 - <<'PY'
import sys
from pathlib import Path

repo_dir = Path("/Volumes/SATA-DATA/SynologyDrive/codex/SenseVoiceDictation/sensevoice-dictation-macos")
sys.path.insert(0, str(repo_dir))

from model_config_layout import build_model_config_sections

sections = build_model_config_sections()
assert [section.key for section in sections] == ["core", "text", "hotwords"], sections

core_keys = [item.key for item in sections[0].items]
assert core_keys == [
    "language",
    "sample_rate",
    "channels",
    "paste_delay_ms",
    "idle_unload_seconds",
], core_keys

text_keys = [item.key for item in sections[1].items]
assert text_keys == [
    "enable_beep",
    "use_itn",
    "merge_vad",
    "remove_emoji",
], text_keys

hotword_keys = [item.key for item in sections[2].items]
assert hotword_keys == ["hotwords"], hotword_keys

assert sections[0].title_key == "model_config_section_core"
assert sections[1].title_key == "model_config_section_text"
assert sections[2].title_key == "model_config_section_hotwords"

print("[PASS] model config layout")
PY
