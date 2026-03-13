#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import ast

repo = Path("/Volumes/SATA-DATA/SynologyDrive/codex/SenseVoiceDictation/sensevoice-dictation-macos")
source = (repo / "menubar_dictation_app.py").read_text(encoding="utf-8")
module = ast.parse(source)

i18n = None
for node in module.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "I18N":
                i18n = ast.literal_eval(node.value)
                break
    if i18n is not None:
        break

assert i18n is not None, "I18N dictionary not found"
assert i18n["model_config_intro"]["zh"] == ""
assert i18n["model_config_intro"]["en"] == ""

def tr_for(lang: str, key: str) -> str:
    item = i18n.get(key)
    if not item:
        return key
    if lang in item:
        return item[lang]
    if "en" in item:
        return item["en"]
    return key

assert tr_for("zh", "model_config_intro") == ""
assert tr_for("en", "model_config_intro") == ""

print("[PASS] i18n empty string")
PY
