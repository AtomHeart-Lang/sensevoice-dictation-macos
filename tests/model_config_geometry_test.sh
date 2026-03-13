#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

python3 - <<'PY'
import sys
from pathlib import Path

repo_dir = Path("/Volumes/SATA-DATA/SynologyDrive/codex/SenseVoiceDictation/sensevoice-dictation-macos")
sys.path.insert(0, str(repo_dir))

from model_config_layout import build_model_config_dialog_layout

layout = build_model_config_dialog_layout()

assert layout.panel_w == 476
assert layout.panel_h == 790

left_margin = layout.card_x
right_margin = layout.panel_w - layout.card_x - layout.card_w
assert left_margin == 28, left_margin
assert right_margin == 8, right_margin

icon_mid_y = layout.icon_y + (layout.icon_size / 2.0)
title_mid_y = layout.title_y + (layout.title_h / 2.0)
assert abs(icon_mid_y - title_mid_y) <= 0.5, (icon_mid_y, title_mid_y)

assert layout.title_font_size == 16
assert layout.field_label_font_size == 13
assert layout.core_help_x == 44
assert layout.toggle_help_x == 44

print("[PASS] model config geometry")
PY
