#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import sys
from pathlib import Path

repo_dir = Path("/Volumes/SATA-DATA/SynologyDrive/codex/SenseVoiceDictation/sensevoice-dictation-macos")
sys.path.insert(0, str(repo_dir))

from hotkey_dialog_layout import (
    build_hotkey_settings_actions,
    build_hotkey_settings_sections,
)

sections = build_hotkey_settings_sections()
assert [section.key for section in sections] == ["mode", "current"], sections
assert sections[0].title_key == "hotkey_dialog_section_mode"
assert sections[1].title_key == "hotkey_dialog_section_current"

mode_items = [item.key for item in sections[0].items]
assert mode_items == ["mode_keyboard", "mode_mouse"], mode_items

current_items = [item.key for item in sections[1].items]
assert current_items == ["keyboard_hotkey", "mouse_button"], current_items

actions = build_hotkey_settings_actions()
assert [action.key for action in actions] == ["set_keyboard", "set_mouse", "save"], actions
assert [action.label_key for action in actions] == ["menu_set_hotkey", "menu_set_mouse", "save"]
assert actions[-1].emphasis == "primary"

print("[PASS] hotkey dialog layout")
PY
