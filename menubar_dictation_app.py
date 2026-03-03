#!/usr/bin/env python3
import atexit
import fcntl
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
import pyperclip
import Quartz
import rumps
import sounddevice as sd
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSImage
from Foundation import NSBundle
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from pynput import keyboard, mouse

try:
    import tomllib
except ModuleNotFoundError as exc:
    raise RuntimeError("Python 3.11+ is required") from exc


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.toml"
UI_SETTINGS_PATH = APP_DIR / "ui_settings.json"
LOG_PATH = APP_DIR / "menubar_debug.log"
LOCK_PATH = APP_DIR / "menubar_app.lock"
MODEL_NAME = "iic/SenseVoiceSmall"
APP_ICON = str((APP_DIR / "assets" / "mic_menu_icon.png").resolve())
APP_BUILD = "2026-03-03-b13"
LOCK_FD = None
EVENT_TAP_LOCATION = Quartz.kCGSessionEventTap
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]+",
    flags=re.UNICODE,
)
AUTOSTART_PLIST = Path.home() / "Library/LaunchAgents/com.lee.sensevoice.menubar.plist"
AUTOSTART_RUNNER = (
    Path.home() / "Library/Application Support/SenseVoiceDictation/autostart_runner.sh"
)
ENABLE_AUTOSTART_SCRIPT = APP_DIR / "enable_autostart.sh"
DISABLE_AUTOSTART_SCRIPT = APP_DIR / "disable_autostart.sh"
MODEL_CACHE_DIRS = [
    Path.home() / ".cache/modelscope/hub/models/iic/SenseVoiceSmall",
    Path.home() / ".cache/modelscope/hub/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
]

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True,
)
logging.info("menubar app module loaded, python=%s", sys.executable)


def _applescript_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def ui_alert(message: str, title: str = "SenseVoice Dictation") -> None:
    icon_clause = ""
    if Path(APP_ICON).exists():
        icon_clause = f' with icon POSIX file "{_applescript_escape(APP_ICON)}"'
    script = (
        f'display dialog "{_applescript_escape(message)}" '
        f'with title "{_applescript_escape(title)}" '
        f'buttons {{"OK"}} default button "OK"{icon_clause}'
    )
    subprocess.run(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def ui_prompt_text(
    message: str,
    title: str,
    default_text: str = "",
    ok_text: str = "保存",
    cancel_text: str = "取消",
) -> Optional[str]:
    icon_clause = ""
    if Path(APP_ICON).exists():
        icon_clause = f' with icon POSIX file "{_applescript_escape(APP_ICON)}"'
    script = (
        f'display dialog "{_applescript_escape(message)}" '
        f'with title "{_applescript_escape(title)}" '
        f'default answer "{_applescript_escape(default_text)}" '
        f'buttons {{"{_applescript_escape(cancel_text)}","{_applescript_escape(ok_text)}"}} '
        f'default button "{_applescript_escape(ok_text)}" '
        f'cancel button "{_applescript_escape(cancel_text)}"{icon_clause}\n'
        "text returned of result"
    )
    proc = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


@dataclass
class CoreConfig:
    language: str = "auto"
    sample_rate: int = 16000
    channels: int = 1
    paste_delay_ms: int = 40
    enable_beep: bool = True
    use_itn: bool = False
    batch_size_s: int = 10
    merge_vad: bool = False
    remove_emoji: bool = True


@dataclass
class UISettings:
    schema_version: int = 2
    trigger_mode: str = "keyboard"  # keyboard|mouse
    keyboard_hotkey: str = "<ctrl>+<alt>+<space>"
    mouse_button: str = "x1"  # middle|x1|x2|button5..button24
    enable_dictation_on_app_start: bool = True


def load_core_config() -> CoreConfig:
    if not CONFIG_PATH.exists():
        return CoreConfig()
    with open(CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)
    return CoreConfig(
        language=str(data.get("language", "auto")),
        sample_rate=int(data.get("sample_rate", 16000)),
        channels=int(data.get("channels", 1)),
        paste_delay_ms=int(data.get("paste_delay_ms", 40)),
        enable_beep=bool(data.get("enable_beep", True)),
        use_itn=bool(data.get("use_itn", False)),
        batch_size_s=int(data.get("batch_size_s", 10)),
        merge_vad=bool(data.get("merge_vad", False)),
        remove_emoji=bool(data.get("remove_emoji", True)),
    )


def save_core_config(config: CoreConfig) -> None:
    hotkey = "<ctrl>+<alt>+<space>"
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "rb") as f:
                data = tomllib.load(f)
            hotkey = str(data.get("hotkey", hotkey))
        except Exception:
            pass

    def b(v: bool) -> str:
        return "true" if v else "false"

    language = config.language.replace('"', "").strip() or "auto"
    content = (
        "# Global hotkey format follows pynput format.\n"
        "# Common examples:\n"
        "#   <ctrl>+<alt>+<space>\n"
        "#   <cmd>+<shift>+v\n"
        "#   <ctrl>+<option>+r\n"
        f'hotkey = "{hotkey}"\n\n'
        "# SenseVoice language: auto, zh, en, yue, ja, ko, nospeech\n"
        '# For better Chinese accuracy, prefer "zh" instead of "auto".\n'
        f'language = "{language}"\n\n'
        "# Audio configuration\n"
        f"sample_rate = {int(config.sample_rate)}\n"
        f"channels = {int(config.channels)}\n\n"
        "# Paste behavior (actual runtime clamps this into 15~60ms)\n"
        f"paste_delay_ms = {int(config.paste_delay_ms)}\n\n"
        "# Enable system sound when start/stop recording\n"
        f"enable_beep = {b(bool(config.enable_beep))}\n\n"
        "# SenseVoice inference options\n"
        "# ITN: normalize numbers/date etc., may improve readability in some cases.\n"
        f"use_itn = {b(bool(config.use_itn))}\n"
        "# seconds per decode batch; higher=faster, lower=usually better segmentation stability.\n"
        "# recommended: 6~12\n"
        f"batch_size_s = {int(config.batch_size_s)}\n"
        "# false=keep VAD segments (usually better punctuation/pauses), true=merge for possible speed gain.\n"
        f"merge_vad = {b(bool(config.merge_vad))}\n\n"
        "# Remove emoji symbols from final pasted text.\n"
        f"remove_emoji = {b(bool(config.remove_emoji))}\n"
    )
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def ui_edit_model_config(current: CoreConfig) -> Optional[CoreConfig]:
    script = r"""
import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

data = json.loads(sys.stdin.read() or "{}")
state = {"result": None}

root = tk.Tk()
root.title("Model Config")
root.resizable(False, False)
root.geometry("+520+220")

icon_path = os.environ.get("SV_ICON_PATH", "")
if icon_path and os.path.exists(icon_path):
    try:
        icon = tk.PhotoImage(file=icon_path)
        root.iconphoto(True, icon)
        root._icon_ref = icon
    except Exception:
        pass

main = ttk.Frame(root, padding=12)
main.grid(row=0, column=0, sticky="nsew")

labels = {
    "language": "language",
    "sample_rate": "sample_rate",
    "channels": "channels",
    "paste_delay_ms": "paste_delay_ms",
    "batch_size_s": "batch_size_s",
}

language_var = tk.StringVar(value=str(data.get("language", "auto")))
sample_rate_var = tk.StringVar(value=str(data.get("sample_rate", 16000)))
channels_var = tk.StringVar(value=str(data.get("channels", 1)))
paste_delay_var = tk.StringVar(value=str(data.get("paste_delay_ms", 40)))
batch_size_var = tk.StringVar(value=str(data.get("batch_size_s", 10)))

enable_beep_var = tk.BooleanVar(value=bool(data.get("enable_beep", True)))
use_itn_var = tk.BooleanVar(value=bool(data.get("use_itn", False)))
merge_vad_var = tk.BooleanVar(value=bool(data.get("merge_vad", False)))
remove_emoji_var = tk.BooleanVar(value=bool(data.get("remove_emoji", True)))

row = 0
ttk.Label(main, text="All config.toml runtime settings", font=("", 12, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
row += 1

ttk.Label(main, text=labels["language"]).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
language_entry = ttk.Combobox(main, textvariable=language_var, width=24)
language_entry["values"] = ("auto", "zh", "en", "yue", "ja", "ko", "nospeech")
language_entry.grid(row=row, column=1, sticky="ew", pady=3)
row += 1

ttk.Label(main, text=labels["sample_rate"]).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
ttk.Entry(main, textvariable=sample_rate_var, width=26).grid(row=row, column=1, sticky="ew", pady=3)
row += 1

ttk.Label(main, text=labels["channels"]).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
ttk.Entry(main, textvariable=channels_var, width=26).grid(row=row, column=1, sticky="ew", pady=3)
row += 1

ttk.Label(main, text=labels["paste_delay_ms"]).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
ttk.Entry(main, textvariable=paste_delay_var, width=26).grid(row=row, column=1, sticky="ew", pady=3)
row += 1

ttk.Label(main, text=labels["batch_size_s"]).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
ttk.Entry(main, textvariable=batch_size_var, width=26).grid(row=row, column=1, sticky="ew", pady=3)
row += 1

ttk.Checkbutton(main, text="enable_beep", variable=enable_beep_var).grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 2))
row += 1
ttk.Checkbutton(main, text="use_itn", variable=use_itn_var).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
row += 1
ttk.Checkbutton(main, text="merge_vad", variable=merge_vad_var).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
row += 1
ttk.Checkbutton(main, text="remove_emoji", variable=remove_emoji_var).grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 8))
row += 1

ttk.Label(main, text="Tips: batch_size_s 6~12; merge_vad=false for better punctuation stability.", foreground="#666666").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
row += 1

def to_int(raw, name, min_value, max_value):
    try:
        value = int(raw)
    except Exception:
        raise ValueError(f"{name} must be an integer")
    if value < min_value or value > max_value:
        raise ValueError(f"{name} must be in [{min_value}, {max_value}]")
    return value

def on_save():
    try:
        language = language_var.get().strip().lower()
        if not language:
            raise ValueError("language cannot be empty")
        sample_rate = to_int(sample_rate_var.get(), "sample_rate", 8000, 48000)
        channels = to_int(channels_var.get(), "channels", 1, 2)
        paste_delay_ms = to_int(paste_delay_var.get(), "paste_delay_ms", 0, 1000)
        batch_size_s = to_int(batch_size_var.get(), "batch_size_s", 1, 60)
        state["result"] = {
            "language": language,
            "sample_rate": sample_rate,
            "channels": channels,
            "paste_delay_ms": paste_delay_ms,
            "enable_beep": bool(enable_beep_var.get()),
            "use_itn": bool(use_itn_var.get()),
            "batch_size_s": batch_size_s,
            "merge_vad": bool(merge_vad_var.get()),
            "remove_emoji": bool(remove_emoji_var.get()),
        }
        root.quit()
    except Exception as exc:
        messagebox.showerror("Invalid Config", str(exc))

def on_cancel():
    root.quit()

btns = ttk.Frame(main)
btns.grid(row=row, column=0, columnspan=2, sticky="e")
ttk.Button(btns, text="Cancel", command=on_cancel).grid(row=0, column=0, padx=(0, 8))
ttk.Button(btns, text="Save", command=on_save).grid(row=0, column=1)

root.columnconfigure(0, weight=1)
main.columnconfigure(1, weight=1)
root.mainloop()
root.destroy()

if state["result"] is None:
    sys.exit(1)
print(json.dumps(state["result"], ensure_ascii=False))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(asdict(current), ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(APP_DIR),
        env={**os.environ, "SV_ICON_PATH": APP_ICON},
        check=False,
    )
    if proc.returncode != 0:
        if proc.stderr.strip():
            logging.warning("ui_edit_model_config canceled/error: %s", proc.stderr.strip())
        return None
    try:
        data = json.loads(proc.stdout.strip())
        return CoreConfig(
            language=str(data.get("language", current.language)),
            sample_rate=int(data.get("sample_rate", current.sample_rate)),
            channels=int(data.get("channels", current.channels)),
            paste_delay_ms=int(data.get("paste_delay_ms", current.paste_delay_ms)),
            enable_beep=bool(data.get("enable_beep", current.enable_beep)),
            use_itn=bool(data.get("use_itn", current.use_itn)),
            batch_size_s=int(data.get("batch_size_s", current.batch_size_s)),
            merge_vad=bool(data.get("merge_vad", current.merge_vad)),
            remove_emoji=bool(data.get("remove_emoji", current.remove_emoji)),
        )
    except Exception as exc:
        logging.warning("ui_edit_model_config parse failed: %s", exc)
        ui_alert("Model Config 保存失败：返回数据格式无效。")
        return None


def load_ui_settings() -> UISettings:
    if not UI_SETTINGS_PATH.exists():
        settings = UISettings()
        save_ui_settings(settings)
        return settings
    with open(UI_SETTINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    is_legacy = "schema_version" not in data
    settings = UISettings(
        schema_version=int(data.get("schema_version", 2)),
        trigger_mode=str(data.get("trigger_mode", "keyboard")),
        keyboard_hotkey=str(data.get("keyboard_hotkey", "<ctrl>+<alt>+<space>")),
        mouse_button=str(data.get("mouse_button", "x1")),
        enable_dictation_on_app_start=bool(
            data.get("enable_dictation_on_app_start", True if is_legacy else True)
        ),
    )
    if is_legacy:
        settings.enable_dictation_on_app_start = True
        save_ui_settings(settings)
    legacy_mouse = settings.mouse_button.strip().lower().replace(" ", "")
    if legacy_mouse in {
        "left",
        "right",
        "button0",
        "button1",
        "primary",
        "secondary",
        "leftclick",
        "rightclick",
    }:
        settings.mouse_button = "x1"
        save_ui_settings(settings)
    return settings


def save_ui_settings(settings: UISettings) -> None:
    with open(UI_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, indent=2, ensure_ascii=False)


def normalize_keyboard_hotkey(value: str) -> str:
    raw = value.strip().lower().replace(" ", "")
    raw = raw.replace("<option>", "<alt>")
    raw = raw.replace("option", "alt") if raw == "option" else raw
    if not raw:
        return "<ctrl>+<alt>+<space>"
    if "+" in raw or "<" in raw:
        return raw
    # single key support, e.g. "f8" or "r"
    return f"<{raw}>" if len(raw) > 1 else raw


MOD_ORDER = ["<ctrl>", "<alt>", "<cmd>", "<shift>"]
KEYCODE_TOKEN_MAP = {
    0: "a",
    1: "s",
    2: "d",
    3: "f",
    4: "h",
    5: "g",
    6: "z",
    7: "x",
    8: "c",
    9: "v",
    11: "b",
    12: "q",
    13: "w",
    14: "e",
    15: "r",
    16: "y",
    17: "t",
    18: "1",
    19: "2",
    20: "3",
    21: "4",
    22: "6",
    23: "5",
    24: "=",
    25: "9",
    26: "7",
    27: "-",
    28: "8",
    29: "0",
    30: "]",
    31: "o",
    32: "u",
    33: "[",
    34: "i",
    35: "p",
    37: "l",
    38: "j",
    39: "'",
    40: "k",
    41: ";",
    42: "\\",
    43: ",",
    44: "/",
    45: "n",
    46: "m",
    47: ".",
    49: "<space>",
    50: "`",
    36: "<enter>",
    48: "<tab>",
    51: "<backspace>",
    53: "<esc>",
    117: "<delete>",
    115: "<home>",
    119: "<end>",
    116: "<pgup>",
    121: "<pgdn>",
    123: "<left>",
    124: "<right>",
    125: "<down>",
    126: "<up>",
    122: "<f1>",
    120: "<f2>",
    99: "<f3>",
    118: "<f4>",
    96: "<f5>",
    97: "<f6>",
    98: "<f7>",
    100: "<f8>",
    101: "<f9>",
    109: "<f10>",
    103: "<f11>",
    111: "<f12>",
    105: "<f13>",
    107: "<f14>",
    113: "<f15>",
    106: "<f16>",
    64: "<f17>",
    79: "<f18>",
    80: "<f19>",
}
MOD_KEY_MAP = {
    keyboard.Key.ctrl: "<ctrl>",
    keyboard.Key.ctrl_l: "<ctrl>",
    keyboard.Key.ctrl_r: "<ctrl>",
    keyboard.Key.alt: "<alt>",
    keyboard.Key.alt_l: "<alt>",
    keyboard.Key.alt_r: "<alt>",
    keyboard.Key.cmd: "<cmd>",
    keyboard.Key.cmd_l: "<cmd>",
    keyboard.Key.cmd_r: "<cmd>",
    keyboard.Key.shift: "<shift>",
    keyboard.Key.shift_l: "<shift>",
    keyboard.Key.shift_r: "<shift>",
}
SPECIAL_KEY_MAP = {
    keyboard.Key.space: "<space>",
    keyboard.Key.enter: "<enter>",
    keyboard.Key.tab: "<tab>",
    keyboard.Key.esc: "<esc>",
    keyboard.Key.backspace: "<backspace>",
    keyboard.Key.delete: "<delete>",
}


def key_to_token(key) -> Optional[str]:
    if key in MOD_KEY_MAP:
        return MOD_KEY_MAP[key]
    if key in SPECIAL_KEY_MAP:
        return SPECIAL_KEY_MAP[key]

    if isinstance(key, keyboard.KeyCode) and key.char:
        return key.char.lower()

    name = getattr(key, "name", None)
    if name:
        name = name.lower()
        if name.startswith("f") and name[1:].isdigit():
            return f"<{name}>"
    return None


def mods_from_flags(flags: int) -> List[str]:
    mods: List[str] = []
    if flags & Quartz.kCGEventFlagMaskControl:
        mods.append("<ctrl>")
    if flags & Quartz.kCGEventFlagMaskAlternate:
        mods.append("<alt>")
    if flags & Quartz.kCGEventFlagMaskCommand:
        mods.append("<cmd>")
    if flags & Quartz.kCGEventFlagMaskShift:
        mods.append("<shift>")
    return mods


def ensure_listen_permission() -> bool:
    ok = bool(Quartz.CGPreflightListenEventAccess())
    if ok:
        return True

    # Try to trigger system prompt once.
    try:
        Quartz.CGRequestListenEventAccess()
    except Exception:
        pass

    ok = bool(Quartz.CGPreflightListenEventAccess())
    if not ok:
        logging.warning("listen permission missing: Input Monitoring/Accessibility not granted")
    return ok


def is_os_autostart_enabled() -> bool:
    return AUTOSTART_PLIST.exists()


def is_os_autostart_legacy() -> bool:
    if not AUTOSTART_PLIST.exists():
        return False
    try:
        content = AUTOSTART_PLIST.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return str(AUTOSTART_RUNNER) not in content


def set_os_autostart_enabled(enable: bool) -> None:
    script = ENABLE_AUTOSTART_SCRIPT if enable else DISABLE_AUTOSTART_SCRIPT
    if not script.exists():
        raise RuntimeError(f"Autostart script not found: {script}")
    proc = subprocess.run(
        ["/bin/bash", str(script)],
        cwd=str(APP_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        if details:
            raise RuntimeError(
                f"autostart script failed with exit {proc.returncode}: {details}"
            )
        raise RuntimeError(f"autostart script failed with exit {proc.returncode}")


def button_number_to_name(button_number: int) -> str:
    mapping = {
        0: "left",
        1: "right",
        2: "middle",
        3: "x1",
        4: "x2",
    }
    return mapping.get(button_number, f"button{button_number}")


def capture_keyboard_hotkey(timeout_s: float = 8.0):
    logging.info("capture_keyboard_hotkey: start")
    result = {"value": None, "err": None}
    event_mask = 1 << Quartz.kCGEventKeyDown
    runloop_ref = {"loop": None}
    tap_ref = {"tap": None}

    def handler(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventTapDisabledByTimeout and tap_ref["tap"] is not None:
            Quartz.CGEventTapEnable(tap_ref["tap"], True)
            return event

        keycode = int(Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode))
        token = KEYCODE_TOKEN_MAP.get(keycode)
        if token is None:
            return event
        if token == "<esc>":
            if runloop_ref["loop"] is not None:
                Quartz.CFRunLoopStop(runloop_ref["loop"])
            return event

        flags = int(Quartz.CGEventGetFlags(event))
        mods = mods_from_flags(flags)
        hotkey = "+".join(mods + [token]) if mods else token
        try:
            keyboard.HotKey.parse(hotkey)
        except Exception:
            return event
        result["value"] = hotkey
        if runloop_ref["loop"] is not None:
            Quartz.CFRunLoopStop(runloop_ref["loop"])
        return event

    try:
        tap_ref["tap"] = Quartz.CGEventTapCreate(
            EVENT_TAP_LOCATION,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            handler,
            None,
        )
        if tap_ref["tap"] is None:
            result["err"] = "Keyboard event tap creation failed."
        else:
            source = Quartz.CFMachPortCreateRunLoopSource(None, tap_ref["tap"], 0)
            runloop_ref["loop"] = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(runloop_ref["loop"], source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap_ref["tap"], True)
            start = time.time()
            while result["value"] is None and (time.time() - start) < timeout_s:
                Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.1, False)
    except Exception as exc:
        result["err"] = f"Keyboard capture crashed: {exc}"
    finally:
        try:
            if runloop_ref["loop"] is not None:
                Quartz.CFRunLoopStop(runloop_ref["loop"])
        except Exception:
            pass
    if result["value"]:
        logging.info("capture_keyboard_hotkey: captured=%s", result["value"])
    elif result["err"]:
        logging.warning("capture_keyboard_hotkey: error=%s", result["err"])
    else:
        logging.info("capture_keyboard_hotkey: timeout")
    return result["value"], result["err"]


def prompt_hotkey_text_fallback(current_value: str) -> Optional[str]:
    text = ui_prompt_text(
        message="手动输入快捷键（例如 <ctrl>+<alt>+<space> 或 f8）",
        title="Set Keyboard Hotkey (Manual)",
        default_text=current_value,
        ok_text="保存",
        cancel_text="取消",
    )
    if text is None:
        return None
    value = normalize_keyboard_hotkey(text)
    if not is_hotkey_supported(value):
        ui_alert("快捷键格式无效或当前版本不支持该按键。")
        return None
    return value


def is_hotkey_supported(hotkey: str) -> bool:
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        return False
    key_token = parts[-1]
    mods = set(parts[:-1])
    allowed_mods = {"<ctrl>", "<alt>", "<cmd>", "<shift>"}
    if not mods.issubset(allowed_mods):
        return False
    return key_token in KEYCODE_TOKEN_MAP.values()


def normalize_mouse_button(value: str) -> Optional[str]:
    raw = value.strip().lower().replace(" ", "")
    alias_map = {
        "middleclick": "middle",
        "wheelclick": "middle",
        "xbutton1": "x1",
        "xbutton2": "x2",
    }
    raw = alias_map.get(raw, raw)

    direct = {"middle", "x1", "x2"}
    if raw in direct:
        return raw

    if raw.startswith("button") and raw[6:].isdigit():
        idx = int(raw[6:])
        if idx in (0, 1):
            return None
        if idx == 2:
            return "middle"
        if idx == 3:
            return "x1"
        if idx == 4:
            return "x2"
        if idx >= 5:
            return f"button{idx}"
    return None


def prompt_mouse_text_fallback(current_value: str) -> Optional[str]:
    text = ui_prompt_text(
        message="手动输入鼠标触发键（例如 x1、x2、middle、button8）。\n不支持 left/right。",
        title="Set Mouse Button (Manual)",
        default_text=current_value,
        ok_text="保存",
        cancel_text="取消",
    )
    if text is None:
        return None
    return normalize_mouse_button(text)


def acquire_single_instance() -> bool:
    global LOCK_FD
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return False
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    LOCK_FD = lock_file
    return True


def release_single_instance() -> None:
    global LOCK_FD
    if LOCK_FD is None:
        return
    try:
        fcntl.flock(LOCK_FD.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        LOCK_FD.close()
    except Exception:
        pass
    LOCK_FD = None


def capture_mouse_button(timeout_s: float = 8.0, tap_location: Optional[int] = None):
    if tap_location is None:
        tap_location = EVENT_TAP_LOCATION
    logging.info("capture_mouse_button: start tap_location=%s", tap_location)
    result = {"value": None, "err": None}
    done = threading.Event()
    started = threading.Event()

    def loop():
        event_mask = (
            (1 << Quartz.kCGEventLeftMouseDown)
            | (1 << Quartz.kCGEventLeftMouseUp)
            | (1 << Quartz.kCGEventRightMouseDown)
            | (1 << Quartz.kCGEventRightMouseUp)
            | (1 << Quartz.kCGEventOtherMouseDown)
            | (1 << Quartz.kCGEventOtherMouseUp)
        )
        runloop_ref = {"loop": None}

        def handler(proxy, event_type, event, refcon):
            if event_type in (
                Quartz.kCGEventTapDisabledByTimeout,
                getattr(Quartz, "kCGEventTapDisabledByUserInput", -1),
            ) and tap_ref["tap"] is not None:
                Quartz.CGEventTapEnable(tap_ref["tap"], True)
                return event
            button_no = int(
                Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventButtonNumber)
            )
            mapped = button_number_to_name(button_no)
            normalized = normalize_mouse_button(mapped)
            logging.info(
                "capture_mouse_button: event_type=%s button_no=%s mapped=%s normalized=%s",
                event_type,
                button_no,
                mapped,
                normalized,
            )
            if normalized is None:
                return event
            result["value"] = normalized
            done.set()
            if runloop_ref["loop"] is not None:
                Quartz.CFRunLoopStop(runloop_ref["loop"])
            return event

        tap_ref = {"tap": None}
        tap_ref["tap"] = Quartz.CGEventTapCreate(
            tap_location,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            handler,
            None,
        )
        if tap_ref["tap"] is None:
            result["err"] = "Mouse event tap creation failed. Check Accessibility + Input Monitoring."
            done.set()
            started.set()
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap_ref["tap"], 0)
        runloop_ref["loop"] = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(runloop_ref["loop"], source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap_ref["tap"], True)
        started.set()

        start = time.time()
        while not done.is_set() and (time.time() - start) < timeout_s:
            Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.1, False)

        if runloop_ref["loop"] is not None:
            Quartz.CFRunLoopStop(runloop_ref["loop"])

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    started.wait(timeout=1.0)
    done.wait(timeout=timeout_s + 0.5)
    if result["value"]:
        logging.info("capture_mouse_button: captured=%s tap_location=%s", result["value"], tap_location)
    elif result["err"]:
        logging.warning("capture_mouse_button: error=%s tap_location=%s", result["err"], tap_location)
    else:
        logging.info("capture_mouse_button: timeout tap_location=%s", tap_location)
    return result["value"], result["err"]


def capture_mouse_button_pynput(timeout_s: float = 6.0):
    logging.info("capture_mouse_button_pynput: start")
    result = {"value": None, "err": None}
    done = threading.Event()
    listener_ref = {"listener": None}

    def on_click(x, y, button, pressed):
        if not pressed:
            return True
        name = getattr(button, "name", str(button))
        token = str(name).lower().replace("button.", "")
        normalized = normalize_mouse_button(token)
        # Some drivers expose auxiliary buttons as unknown in pynput on macOS.
        # Keep logs explicit and let Quartz path handle raw button numbers.
        logging.info(
            "capture_mouse_button_pynput: token=%s normalized=%s",
            token,
            normalized,
        )
        if normalized is None:
            return True
        result["value"] = normalized
        done.set()
        return False

    try:
        listener_ref["listener"] = mouse.Listener(on_click=on_click, suppress=False)
        listener_ref["listener"].start()
        done.wait(timeout=timeout_s)
    except Exception as exc:
        result["err"] = f"pynput mouse capture crashed: {exc}"
    finally:
        try:
            if listener_ref["listener"] is not None:
                listener_ref["listener"].stop()
                listener_ref["listener"].join(timeout=0.5)
        except Exception:
            pass
    if result["value"]:
        logging.info("capture_mouse_button_pynput: captured=%s", result["value"])
    elif result["err"]:
        logging.warning("capture_mouse_button_pynput: error=%s", result["err"])
    else:
        logging.info("capture_mouse_button_pynput: timeout")
    return result["value"], result["err"]


def choose_mouse_button_with_capture(current_value: str) -> Optional[str]:
    ui_alert(
        "点击 OK 后开始捕获 20 秒。\n"
        "请按你要设置的鼠标键；左键/右键会忽略。"
    )
    captured, err = capture_mouse_button(timeout_s=20.0, tap_location=EVENT_TAP_LOCATION)
    if not captured:
        hid_location = getattr(Quartz, "kCGHIDEventTap", None)
        if hid_location is not None:
            hid_captured, hid_err = capture_mouse_button(timeout_s=8.0, tap_location=hid_location)
            if hid_captured:
                captured = hid_captured
                err = None
            elif err is None:
                err = hid_err
    if not captured:
        fallback_captured, fallback_err = capture_mouse_button_pynput(timeout_s=12.0)
        if fallback_captured:
            captured = fallback_captured
            err = None
        elif err is None:
            err = fallback_err
    if captured:
        edited = ui_prompt_text(
            message=f"已识别到鼠标按键: {captured}\n可直接保存或手动修改。",
            title="Set Mouse Button",
            default_text=captured,
            ok_text="保存",
            cancel_text="取消",
        )
        if edited is None:
            return None
        normalized = normalize_mouse_button(edited)
        if normalized is None:
            ui_alert("鼠标按键格式无效。支持 middle、x1、x2、buttonN（N>=2，且不含 0/1）。")
            return None
        return normalized

    kb_value, _ = capture_keyboard_hotkey(timeout_s=4.0)
    if kb_value:
        ui_alert(
            "未检测到可用鼠标按钮，但检测到按键组合："
            f"{kb_value}\n"
            "这通常表示鼠标驱动已把侧键映射为键盘快捷键。\n"
            "你可以：\n"
            "1) 在 Logi Options+ 把该按键改为 Generic Button；或\n"
            "2) 直接用 Set Keyboard Hotkey 设置这个组合。"
        )

    if err:
        ui_alert(f"自动识别失败：{err}\n将进入手动输入。")
    else:
        ui_alert("未识别到可用鼠标按键（左键/右键会被忽略）。将进入手动输入。")
    return prompt_mouse_text_fallback(current_value)


class DictationEngine:
    def __init__(self, config: CoreConfig, status_cb: Callable[[str], None]):
        self.config = config
        self.status_cb = status_cb
        self.model = None
        self.model_loading = False
        self.stream = None
        self.frames: List[np.ndarray] = []
        self.lock = threading.Lock()
        self.recording = False
        self.processing = False
        self.shutdown_flag = False

    def _set_status(self, status: str) -> None:
        self.status_cb(status)

    def _beep(self, kind: str = "default") -> None:
        if not self.config.enable_beep:
            return
        sound_file = "/System/Library/Sounds/Pop.aiff"
        if kind == "start":
            sound_file = "/System/Library/Sounds/Tink.aiff"
        elif kind == "stop":
            sound_file = "/System/Library/Sounds/Pop.aiff"
        subprocess.Popen(
            ["afplay", sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def warmup_async(self) -> None:
        with self.lock:
            if self.model is not None or self.model_loading:
                return
            self.model_loading = True
        threading.Thread(target=self._load_model_worker, daemon=True).start()

    def _load_model_worker(self) -> None:
        self._set_status("LOADING")
        try:
            model = AutoModel(
                model=MODEL_NAME,
                trust_remote_code=False,
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device="cpu",
                disable_update=True,
            )
            with self.lock:
                self.model = model
        except Exception:
            self._set_status("ERROR")
        finally:
            with self.lock:
                self.model_loading = False
            if not self.shutdown_flag and self.model is not None and not self.recording and not self.processing:
                self._set_status("READY")

    def _ensure_model(self) -> bool:
        with self.lock:
            if self.model is not None:
                return True
            if self.model_loading:
                return False
        self.warmup_async()
        return False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass
        with self.lock:
            if self.recording and not self.shutdown_flag:
                self.frames.append(indata.copy())

    def _merge_frames(self):
        with self.lock:
            if not self.frames:
                return None
            return np.concatenate(self.frames, axis=0)

    @staticmethod
    def _trim_silence(audio: np.ndarray, sample_rate: int) -> np.ndarray:
        if audio is None or audio.size == 0:
            return audio
        arr = np.squeeze(audio).astype(np.float32)
        if arr.ndim != 1 or arr.size < max(sample_rate // 5, 1):
            return arr
        abs_arr = np.abs(arr)
        active = np.flatnonzero(abs_arr > 0.008)
        if active.size == 0:
            return arr
        pad = max(int(sample_rate * 0.08), 1)
        start = max(int(active[0]) - pad, 0)
        end = min(int(active[-1]) + pad + 1, arr.size)
        if start == 0 and end == arr.size:
            return arr
        trimmed = arr[start:end]
        logging.info("trim_silence: raw=%d trimmed=%d", arr.size, trimmed.size)
        return trimmed

    def _paste_text(self, text: str) -> None:
        pyperclip.copy(text)
        # Cap delay so stale configs do not add visible latency.
        delay_ms = min(max(self.config.paste_delay_ms, 15), 60)
        time.sleep(delay_ms / 1000)
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    @staticmethod
    def _cleanup_text(text: str, remove_emoji: bool) -> str:
        if remove_emoji:
            text = EMOJI_RE.sub("", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def start_recording(self) -> None:
        if not self._ensure_model():
            return

        with self.lock:
            if self.recording or self.processing or self.shutdown_flag:
                return
            self.frames = []
            self.recording = True
        # Update UI state immediately, don't wait for stream startup.
        self._set_status("RECORDING")

        try:
            self.stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype="float32",
                callback=self._audio_callback,
            )
            self.stream.start()
        except Exception:
            with self.lock:
                self.recording = False
            self._set_status("ERROR")
            return

        self._beep("start")

    def stop_recording(self) -> None:
        with self.lock:
            if not self.recording:
                return
            self.recording = False
        stop_ts = time.monotonic()
        logging.info("stop_recording: requested")

        # Reflect stop action immediately, before any potentially blocking audio teardown.
        self._set_status("TRANSCRIBING")

        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        audio = self._merge_frames()
        if audio is None or len(audio) == 0:
            self._set_status("READY")
            return

        threading.Thread(
            target=self._transcribe_worker,
            args=(audio, stop_ts),
            daemon=True,
        ).start()
        self._beep("stop")

    def _transcribe_worker(self, audio: np.ndarray, stop_ts: Optional[float] = None) -> None:
        with self.lock:
            if self.processing or self.shutdown_flag:
                return
            self.processing = True

        self._set_status("TRANSCRIBING")
        transcribe_start = time.monotonic()
        try:
            pcm = self._trim_silence(audio, self.config.sample_rate)
            result = self.model.generate(
                input=pcm,
                cache={},
                language=self.config.language,
                use_itn=self.config.use_itn,
                batch_size_s=self.config.batch_size_s,
                merge_vad=self.config.merge_vad,
                fs=self.config.sample_rate,
            )
            raw_text = result[0].get("text", "") if result else ""
            text = rich_transcription_postprocess(raw_text)
            text = self._cleanup_text(text, self.config.remove_emoji)
            if text and not self.shutdown_flag:
                self._paste_text(text)
            done_ts = time.monotonic()
            if stop_ts is not None:
                logging.info(
                    "latency stop_to_done=%.3fs transcribe=%.3fs text_len=%d",
                    done_ts - stop_ts,
                    done_ts - transcribe_start,
                    len(text),
                )
        except Exception:
            self._set_status("ERROR")
        finally:
            with self.lock:
                self.processing = False
            if not self.shutdown_flag and not self.recording:
                self._set_status("READY")

    def toggle_recording(self) -> None:
        with self.lock:
            recording_now = self.recording
        if recording_now:
            self.stop_recording()
        else:
            self.start_recording()

    def stop_all(self) -> None:
        with self.lock:
            self.recording = False
            self.shutdown_flag = True

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        with self.lock:
            self.frames = []
            self.model = None
            self.processing = False
            self.model_loading = False


class TriggerController:
    BUTTON_MAP = {
        "middle": 2,
        "x1": 3,
        "x2": 4,
        "button3": 3,
        "button4": 4,
    }

    def __init__(self, callback: Callable[[], None]):
        self.callback = callback
        self.keyboard_thread = None
        self.keyboard_runloop = None
        self.keyboard_tap = None
        self.keyboard_stop_event = threading.Event()
        self.required_mods = set()
        self.required_keycode = None
        self.mouse_thread = None
        self.mouse_runloop = None
        self.mouse_tap = None
        self.mouse_stop_event = threading.Event()
        self._lock = threading.Lock()
        self.last_trigger_ts = 0.0
        self.active_mods = set()
        self.pressed_keycodes = set()
        self.combo_armed = False

    def stop(self) -> None:
        with self._lock:
            self.keyboard_stop_event.set()
            if self.keyboard_runloop is not None:
                Quartz.CFRunLoopStop(self.keyboard_runloop)
            if self.keyboard_thread is not None:
                self.keyboard_thread.join(timeout=1.0)
            self.keyboard_thread = None
            self.keyboard_runloop = None
            self.keyboard_tap = None
            self.required_mods = set()
            self.required_keycode = None
            self.active_mods = set()
            self.pressed_keycodes = set()
            self.combo_armed = False
            self.mouse_stop_event.set()
            if self.mouse_runloop is not None:
                Quartz.CFRunLoopStop(self.mouse_runloop)
            if self.mouse_thread is not None:
                self.mouse_thread.join(timeout=1.0)
            self.mouse_thread = None
            self.mouse_runloop = None
            self.mouse_tap = None

    def start_keyboard(self, hotkey_value: str) -> None:
        self.stop()
        hotkey = normalize_keyboard_hotkey(hotkey_value)
        if not is_hotkey_supported(hotkey):
            raise RuntimeError(f"Unsupported keyboard hotkey: {hotkey}")
        parts = [p for p in hotkey.split("+") if p]
        if not parts:
            raise RuntimeError("Invalid keyboard hotkey")
        key_token = parts[-1].lower()
        mods = {p.lower() for p in parts[:-1]}

        required_keycode = None
        for k, v in KEYCODE_TOKEN_MAP.items():
            if v == key_token:
                required_keycode = k
                break
        if required_keycode is None:
            raise RuntimeError(f"Unsupported key token: {key_token}")

        self.required_keycode = required_keycode
        self.required_mods = mods
        self.active_mods = set()
        self.pressed_keycodes = set()
        self.combo_armed = False
        self.keyboard_stop_event.clear()
        started = threading.Event()
        startup_error = {"err": None}

        def loop():
            try:
                event_mask = (
                    (1 << Quartz.kCGEventKeyDown)
                    | (1 << Quartz.kCGEventKeyUp)
                    | (1 << Quartz.kCGEventFlagsChanged)
                )

                def handler(proxy, event_type, event, refcon):
                    if self.keyboard_stop_event.is_set():
                        return event
                    if event_type in (
                        Quartz.kCGEventTapDisabledByTimeout,
                        getattr(Quartz, "kCGEventTapDisabledByUserInput", -1),
                    ):
                        Quartz.CGEventTapEnable(self.keyboard_tap, True)
                        return event

                    keycode = int(
                        Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                    )
                    flags = int(Quartz.CGEventGetFlags(event))
                    self.active_mods = set(mods_from_flags(flags))

                    if event_type == Quartz.kCGEventKeyDown:
                        is_repeat = int(
                            Quartz.CGEventGetIntegerValueField(
                                event, Quartz.kCGKeyboardEventAutorepeat
                            )
                        )
                        if is_repeat:
                            return event
                        self.pressed_keycodes.add(keycode)
                    elif event_type == Quartz.kCGEventKeyUp:
                        self.pressed_keycodes.discard(keycode)
                    # For flags-changed, no direct key add/remove here; we only refresh modifiers.

                    combo_now = (
                        self.required_keycode in self.pressed_keycodes
                        and self.required_mods.issubset(self.active_mods)
                    )
                    if combo_now and not self.combo_armed:
                        self.combo_armed = True
                        logging.info(
                            "keyboard combo matched keycode=%s required_mods=%s active_mods=%s pressed=%s",
                            self.required_keycode,
                            sorted(self.required_mods),
                            sorted(self.active_mods),
                            sorted(self.pressed_keycodes),
                        )
                        self._fire_callback()
                    elif not combo_now:
                        self.combo_armed = False
                    return event

                self.keyboard_tap = Quartz.CGEventTapCreate(
                    EVENT_TAP_LOCATION,
                    Quartz.kCGHeadInsertEventTap,
                    Quartz.kCGEventTapOptionDefault,
                    event_mask,
                    handler,
                    None,
                )
                if self.keyboard_tap is None:
                    startup_error["err"] = RuntimeError("Failed to create keyboard event tap")
                    started.set()
                    return

                source = Quartz.CFMachPortCreateRunLoopSource(None, self.keyboard_tap, 0)
                self.keyboard_runloop = Quartz.CFRunLoopGetCurrent()
                Quartz.CFRunLoopAddSource(self.keyboard_runloop, source, Quartz.kCFRunLoopCommonModes)
                Quartz.CGEventTapEnable(self.keyboard_tap, True)
                started.set()
                Quartz.CFRunLoopRun()
            except Exception as exc:
                startup_error["err"] = exc
                started.set()

        self.keyboard_thread = threading.Thread(target=loop, daemon=True)
        self.keyboard_thread.start()
        started.wait(timeout=1.5)
        if startup_error["err"] is not None:
            raise startup_error["err"]

    def _fire_callback(self):
        now = time.monotonic()
        # Debounce hotkey repeat so one physical press maps to one toggle.
        if now - self.last_trigger_ts < 0.12:
            return
        self.last_trigger_ts = now
        logging.info("trigger fired")
        # Never block event tap callback thread with recording/transcribe control flow.
        threading.Thread(target=self.callback, daemon=True).start()

    def start_mouse(self, button_name: str) -> None:
        self.stop()
        normalized = normalize_mouse_button(button_name)
        if normalized is None:
            raise RuntimeError(f"Unsupported mouse button: {button_name}")
        if normalized.startswith("button") and normalized[6:].isdigit():
            target_button_number = int(normalized[6:])
        else:
            target_button_number = self.BUTTON_MAP[normalized]
        self.mouse_stop_event.clear()
        started = threading.Event()
        startup_error = {"err": None}

        def loop():
            try:
                event_mask = (
                    (1 << Quartz.kCGEventLeftMouseDown)
                    | (1 << Quartz.kCGEventRightMouseDown)
                    | (1 << Quartz.kCGEventOtherMouseDown)
                )

                def handler(proxy, event_type, event, refcon):
                    if self.mouse_stop_event.is_set():
                        return event
                    if event_type in (
                        Quartz.kCGEventTapDisabledByTimeout,
                        getattr(Quartz, "kCGEventTapDisabledByUserInput", -1),
                    ):
                        Quartz.CGEventTapEnable(self.mouse_tap, True)
                        return event
                    button_no = Quartz.CGEventGetIntegerValueField(
                        event, Quartz.kCGMouseEventButtonNumber
                    )
                    if int(button_no) == target_button_number:
                        self._fire_callback()
                    return event

                self.mouse_tap = Quartz.CGEventTapCreate(
                    EVENT_TAP_LOCATION,
                    Quartz.kCGHeadInsertEventTap,
                    Quartz.kCGEventTapOptionDefault,
                    event_mask,
                    handler,
                    None,
                )
                if self.mouse_tap is None:
                    startup_error["err"] = RuntimeError("Failed to create mouse event tap")
                    started.set()
                    return

                source = Quartz.CFMachPortCreateRunLoopSource(None, self.mouse_tap, 0)
                self.mouse_runloop = Quartz.CFRunLoopGetCurrent()
                Quartz.CFRunLoopAddSource(
                    self.mouse_runloop, source, Quartz.kCFRunLoopCommonModes
                )
                Quartz.CGEventTapEnable(self.mouse_tap, True)
                started.set()
                Quartz.CFRunLoopRun()
            except Exception as exc:
                startup_error["err"] = exc
                started.set()

        self.mouse_thread = threading.Thread(target=loop, daemon=True)
        self.mouse_thread.start()
        started.wait(timeout=1.5)
        if startup_error["err"] is not None:
            raise startup_error["err"]


class SenseVoiceMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__(
            "SV Off",
            icon=APP_ICON if Path(APP_ICON).exists() else None,
            template=True,
            quit_button=None,
        )
        self.core_config = load_core_config()
        self.ui_settings = load_ui_settings()

        self.current_status = "OFF"
        self.dictation_enabled = False
        self.updating_model = False
        self.status_lock = threading.Lock()
        self.pending_alerts: List[str] = []
        self.pending_alerts_lock = threading.Lock()
        self.pending_reenable = False
        self.pending_startup_enable = False
        self.permission_hint_shown = False

        self.engine = DictationEngine(self.core_config, self.on_engine_status)
        self.trigger = TriggerController(self.on_trigger)

        self.status_item = rumps.MenuItem("Status: OFF")
        self.trigger_item = rumps.MenuItem("Trigger: keyboard <ctrl>+<alt>+<space>")
        self.auto_on_item = rumps.MenuItem("Enable Dictation On App Start")
        self.launch_login_item = rumps.MenuItem("Enable Launch At Login")
        self.build_item = rumps.MenuItem(f"Build: {APP_BUILD}")

        self.menu = [
            self.status_item,
            self.trigger_item,
            None,
            "Toggle Dictation",
            "Use Keyboard Trigger",
            "Use Mouse Trigger",
            "Set Keyboard Hotkey",
            "Set Mouse Button",
            "Model Config",
            "Update Model",
            self.auto_on_item,
            self.launch_login_item,
            self.build_item,
            None,
            "Quit App",
        ]

        self.refresh_ui_labels()
        self._migrate_autostart_if_needed()
        self.refresh_ui_labels()

        if self.ui_settings.enable_dictation_on_app_start:
            # Show menubar status immediately, then enable in runloop.
            self.on_engine_status("LOADING")
            self.title = "…"
            self.status_item.title = "Status: LOADING"
            self.engine.warmup_async()
            self.pending_startup_enable = True

    def on_engine_status(self, status: str) -> None:
        with self.status_lock:
            self.current_status = status

    def _queue_alert(self, text: str) -> None:
        with self.pending_alerts_lock:
            self.pending_alerts.append(text)

    def _flush_pending_alert(self) -> None:
        msg = None
        with self.pending_alerts_lock:
            if self.pending_alerts:
                msg = self.pending_alerts.pop(0)
        if msg:
            ui_alert(msg)

    def _flush_pending_actions(self) -> None:
        if self.pending_reenable:
            self.pending_reenable = False
            self.enable_dictation()
        if self.pending_startup_enable:
            self.pending_startup_enable = False
            self.enable_dictation()

    def on_trigger(self) -> None:
        if not self.dictation_enabled or self.updating_model:
            return
        self.engine.toggle_recording()

    def enable_dictation(self) -> None:
        permission_ok = ensure_listen_permission()
        if not permission_ok:
            logging.warning("enable_dictation: preflight permission check failed, continue to probe taps")
        try:
            logging.info("enable_dictation: mode=%s", self.ui_settings.trigger_mode)
            if self.ui_settings.trigger_mode == "mouse":
                self.trigger.start_mouse(self.ui_settings.mouse_button)
            else:
                self.trigger.start_keyboard(self.ui_settings.keyboard_hotkey)
            self.dictation_enabled = True
            self.engine.warmup_async()
            self.on_engine_status("LOADING")
            self.permission_hint_shown = False
        except Exception as exc:
            logging.exception("enable_dictation failed: %s", exc)
            self.dictation_enabled = False
            self.on_engine_status("ERROR")
            if "Failed to create keyboard event tap" in str(exc):
                ui_alert(
                    "无法创建键盘监听（event tap）。这通常是启动器权限归属问题。\n"
                    "请重新创建桌面启动器后再试：\n"
                    "1) ./remove_launcher.sh\n"
                    "2) ./create_launcher.sh\n"
                    "3) 在系统设置中给 “SenseVoice Dictation.app” 重新勾选 Accessibility 和 Input Monitoring。\n"
                    f"当前 Python: {sys.executable}"
                )
            if not permission_ok and not self.permission_hint_shown:
                self.permission_hint_shown = True
                ui_alert(
                    "监听权限可能未生效。请在 系统设置 -> 隐私与安全性 -> Input Monitoring / Accessibility 中"
                    "确认已勾选当前启动器，并重启应用。"
                )

    def disable_dictation(self) -> None:
        self.dictation_enabled = False
        self.trigger.stop()
        self.engine.stop_all()
        self.engine = DictationEngine(self.core_config, self.on_engine_status)
        self.on_engine_status("OFF")

    def refresh_ui_labels(self) -> None:
        mode_text = f"{self.ui_settings.trigger_mode}"
        if self.ui_settings.trigger_mode == "mouse":
            mode_text += f" {self.ui_settings.mouse_button}"
        else:
            mode_text += f" {normalize_keyboard_hotkey(self.ui_settings.keyboard_hotkey)}"
        self.trigger_item.title = f"Trigger: {mode_text}"

        self.auto_on_item.state = 1 if self.ui_settings.enable_dictation_on_app_start else 0
        self.launch_login_item.state = 1 if is_os_autostart_enabled() else 0

    def _migrate_autostart_if_needed(self) -> None:
        if not is_os_autostart_enabled() or not is_os_autostart_legacy():
            return
        try:
            set_os_autostart_enabled(True)
            logging.info("autostart migrated to runner: %s", AUTOSTART_RUNNER)
        except Exception as exc:
            logging.exception("autostart migration failed: %s", exc)
            self._queue_alert(
                "检测到旧版开机自启动配置，自动迁移失败。"
                "请在菜单中关闭再开启一次 “Enable Launch At Login”。"
            )

    def restart_trigger(self) -> None:
        if not self.dictation_enabled:
            return
        try:
            if self.ui_settings.trigger_mode == "mouse":
                self.trigger.start_mouse(self.ui_settings.mouse_button)
            else:
                self.trigger.start_keyboard(self.ui_settings.keyboard_hotkey)
        except Exception:
            self.on_engine_status("ERROR")

    @rumps.timer(0.1)
    def sync_status(self, _):
        self._flush_pending_alert()
        self._flush_pending_actions()
        with self.status_lock:
            status = self.current_status
        title_map = {
            "OFF": "○",
            "LOADING": "…",
            "UPDATING": "⇡",
            "READY": "✓",
            "RECORDING": "●",
            "TRANSCRIBING": "↻",
            "ERROR": "!",
        }
        self.title = title_map.get(status, "•")
        self.status_item.title = f"Status: {status}"

    @rumps.clicked("Toggle Dictation")
    def on_toggle_dictation(self, _):
        if self.dictation_enabled:
            self.disable_dictation()
        else:
            self.enable_dictation()

    @rumps.clicked("Use Keyboard Trigger")
    def on_use_keyboard(self, _):
        logging.info("on_use_keyboard clicked")
        self.ui_settings.trigger_mode = "keyboard"
        save_ui_settings(self.ui_settings)
        self.refresh_ui_labels()
        self.restart_trigger()

    @rumps.clicked("Use Mouse Trigger")
    def on_use_mouse(self, _):
        self.ui_settings.trigger_mode = "mouse"
        save_ui_settings(self.ui_settings)
        self.refresh_ui_labels()
        self.restart_trigger()

    @rumps.clicked("Set Keyboard Hotkey")
    def on_set_hotkey(self, _):
        try:
            logging.info("on_set_hotkey: start")
            was_enabled = self.dictation_enabled
            if was_enabled:
                self.trigger.stop()
            value = prompt_hotkey_text_fallback(self.ui_settings.keyboard_hotkey)
            err = None if value else "manual input canceled/invalid"

            if not value:
                msg = f"No Key Captured. {err}" if err else "No Key Captured."
                ui_alert(msg)
                if was_enabled:
                    self.restart_trigger()
                return

            self.ui_settings.keyboard_hotkey = value
            self.ui_settings.trigger_mode = "keyboard"
            save_ui_settings(self.ui_settings)
            self.refresh_ui_labels()
            if was_enabled:
                self.restart_trigger()
            ui_alert(f"已设置快捷键: {value}")
            logging.info("on_set_hotkey: saved=%s", value)
        except Exception as exc:
            logging.exception("on_set_hotkey crashed: %s", exc)
            ui_alert(f"Set Keyboard Hotkey failed: {exc}")

    @rumps.clicked("Set Mouse Button")
    def on_set_mouse_button(self, _):
        try:
            logging.info("on_set_mouse_button: start")
            was_enabled = self.dictation_enabled
            if was_enabled:
                self.trigger.stop()

            value = choose_mouse_button_with_capture(self.ui_settings.mouse_button)
            if not value:
                ui_alert("No Mouse Button Captured.")
                if was_enabled:
                    self.restart_trigger()
                return

            self.ui_settings.mouse_button = value
            self.ui_settings.trigger_mode = "mouse"
            save_ui_settings(self.ui_settings)
            self.refresh_ui_labels()
            if was_enabled:
                self.restart_trigger()
            ui_alert(f"已设置鼠标按键: {value}")
            logging.info("on_set_mouse_button: saved=%s", value)
        except Exception as exc:
            logging.exception("on_set_mouse_button crashed: %s", exc)
            ui_alert(f"Set Mouse Button failed: {exc}")

    @rumps.clicked("Model Config")
    def on_model_config(self, _):
        try:
            logging.info("on_model_config: open")
            edited = ui_edit_model_config(self.core_config)
            if edited is None:
                return
            save_core_config(edited)
            self.core_config = load_core_config()
            self.engine.config = self.core_config
            logging.info(
                "on_model_config: saved language=%s sample_rate=%s channels=%s use_itn=%s batch_size_s=%s merge_vad=%s remove_emoji=%s",
                self.core_config.language,
                self.core_config.sample_rate,
                self.core_config.channels,
                self.core_config.use_itn,
                self.core_config.batch_size_s,
                self.core_config.merge_vad,
                self.core_config.remove_emoji,
            )
            ui_alert("Model Config 已保存。新参数将从下一次录音开始生效。")
        except Exception as exc:
            logging.exception("on_model_config failed: %s", exc)
            ui_alert(f"Model Config 保存失败: {exc}")

    @rumps.clicked("Update Model")
    def on_update_model(self, _):
        if self.updating_model:
            ui_alert("模型更新已在进行中。")
            return
        self.updating_model = True
        threading.Thread(target=self._update_model_worker, daemon=True).start()

    def _update_model_worker(self) -> None:
        was_enabled = self.dictation_enabled
        try:
            self.on_engine_status("UPDATING")
            self.dictation_enabled = False
            self.trigger.stop()
            self.engine.stop_all()

            removed: List[str] = []
            for path in MODEL_CACHE_DIRS:
                if path.exists():
                    shutil.rmtree(path, ignore_errors=True)
                    removed.append(str(path))
            logging.info("update_model: removed_cache=%s", removed)

            self.engine = DictationEngine(self.core_config, self.on_engine_status)
            self.engine.warmup_async()

            wait_s = 0.0
            while wait_s < 90:
                with self.engine.lock:
                    ready = self.engine.model is not None and not self.engine.model_loading
                if ready:
                    break
                time.sleep(0.2)
                wait_s += 0.2

            with self.engine.lock:
                ready = self.engine.model is not None and not self.engine.model_loading
            if not ready:
                self.on_engine_status("ERROR")
                self._queue_alert("模型更新失败：下载或加载超时，请稍后重试。")
                if was_enabled:
                    self.pending_reenable = True
                return

            if was_enabled:
                if self.ui_settings.trigger_mode == "mouse":
                    self.trigger.start_mouse(self.ui_settings.mouse_button)
                else:
                    self.trigger.start_keyboard(self.ui_settings.keyboard_hotkey)
                self.dictation_enabled = True
                self.on_engine_status("READY")
            else:
                self.on_engine_status("OFF")

            self._queue_alert("模型更新完成。")
            logging.info("update_model: completed")
        except Exception as exc:
            logging.exception("update_model failed: %s", exc)
            self.on_engine_status("ERROR")
            self._queue_alert(f"模型更新失败: {exc}")
            if was_enabled:
                self.pending_reenable = True
        finally:
            self.updating_model = False

    @rumps.clicked("Enable Dictation On App Start")
    def on_toggle_auto_on(self, sender):
        self.ui_settings.enable_dictation_on_app_start = not self.ui_settings.enable_dictation_on_app_start
        save_ui_settings(self.ui_settings)
        self.refresh_ui_labels()

    @rumps.clicked("Enable Launch At Login")
    def on_toggle_launch_at_login(self, sender):
        try:
            target = not is_os_autostart_enabled()
            set_os_autostart_enabled(target)
            self.refresh_ui_labels()
        except Exception as exc:
            logging.exception("toggle launch at login failed: %s", exc)
            ui_alert(f"Failed to update Launch At Login: {exc}")

    @rumps.clicked("Quit App")
    def on_quit(self, _):
        self.trigger.stop()
        self.engine.stop_all()
        rumps.quit_application()


def main() -> None:
    # Keep the app in menu bar mode (hide Dock icon where possible).
    try:
        bundle = NSBundle.mainBundle()
        if bundle is not None and bundle.infoDictionary() is not None:
            bundle.infoDictionary()["LSUIElement"] = "1"
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        # Force app icon for all NSAlert/NSWindow created by rumps (avoid Python rocket icon).
        if Path(APP_ICON).exists():
            icon = NSImage.alloc().initWithContentsOfFile_(APP_ICON)
            if icon is not None:
                app.setApplicationIconImage_(icon)
    except Exception:
        pass

    if not acquire_single_instance():
        logging.info("another instance exists, skip launch")
        return
    atexit.register(release_single_instance)

    app = SenseVoiceMenuBarApp()
    app.run()


if __name__ == "__main__":
    main()
