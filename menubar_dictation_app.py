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
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBezierPath,
    NSBezelBorder,
    NSButton,
    NSControlStateValueOn,
    NSImage,
    NSImageView,
    NSMakeRect,
    NSMakeSize,
    NSProgressIndicator,
    NSProgressIndicatorStyleSpinning,
    NSScrollView,
    NSSwitchButton,
    NSTextField,
    NSTextAlignmentCenter,
    NSTextView,
    NSView,
    NSWindow,
    NSWindowStyleMaskTitled,
    NSBackingStoreBuffered,
)
from Foundation import NSBundle, NSDate, NSLocale, NSRunLoop
from pynput import keyboard, mouse

try:
    import tomllib
except ModuleNotFoundError as exc:
    raise RuntimeError("Python 3.11+ is required") from exc


APP_DIR = Path(__file__).resolve().parent
APP_SUPPORT_DIR = Path.home() / "Library/Application Support/SenseVoiceDictation"
CONFIG_PATH = APP_DIR / "config.toml"
LEGACY_UI_SETTINGS_PATH = APP_DIR / "ui_settings.json"
UI_SETTINGS_PATH = APP_SUPPORT_DIR / "ui_settings.json"
LOG_PATH = APP_DIR / "menubar_debug.log"
LOCK_PATH = APP_DIR / "menubar_app.lock"
MODEL_NAME = "FunAudioLLM/Fun-ASR-Nano-2512"
VAD_MODEL_NAME = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
FUNASR_RUNTIME_DIR = APP_DIR / "funasr_nano_runtime"
FUNASR_REMOTE_CODE_PATH = FUNASR_RUNTIME_DIR / "model.py"
MENU_ICON = str((APP_DIR / "assets" / "mic_menu_icon.png").resolve())
APP_ICON = str((APP_DIR / "assets" / "app_launcher_icon.png").resolve())
APP_BUILD = "2026-03-05-b14"
LOCK_FD = None
EVENT_TAP_LOCATION = Quartz.kCGSessionEventTap
DEFAULT_NCPU = max(1, int(os.environ.get("SVD_NCPU", "2")))
_FUNASR_IMPORT_LOCK = threading.Lock()
_AUTOMODEL_CLS = None
_POSTPROCESS_FN = None
CJK_CHAR_CLASS = r"\u3400-\u4dbf\u4e00-\u9fff"
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
AUTOSTART_PLIST = Path.home() / "Library/LaunchAgents/com.lee.funasr.menubar.plist"
LEGACY_AUTOSTART_PLIST = Path.home() / "Library/LaunchAgents/com.lee.sensevoice.menubar.plist"
AUTOSTART_RUNNER = (
    Path.home() / "Library/Application Support/SenseVoiceDictation/autostart_runner.sh"
)
AUTOSTART_RUNNER_VERSION = "3"
ENABLE_AUTOSTART_SCRIPT = APP_DIR / "enable_autostart.sh"
DISABLE_AUTOSTART_SCRIPT = APP_DIR / "disable_autostart.sh"
MODEL_CACHE_DIRS = [
    Path.home() / ".cache/modelscope/hub/models/FunAudioLLM/Fun-ASR-Nano-2512",
    Path.home() / ".cache/modelscope/hub/models/iic/SenseVoiceSmall",
    Path.home() / ".cache/modelscope/hub/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
]
_APP_ICON_CACHE: Optional[NSImage] = None
_APP_ICON_ROUNDED_CACHE: Optional[NSImage] = None

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True,
)
logging.info("menubar app module loaded, python=%s", sys.executable)


def ensure_funasr_modules_loaded() -> None:
    global _AUTOMODEL_CLS, _POSTPROCESS_FN
    if _AUTOMODEL_CLS is not None and _POSTPROCESS_FN is not None:
        return
    with _FUNASR_IMPORT_LOCK:
        if _AUTOMODEL_CLS is not None and _POSTPROCESS_FN is not None:
            return
        import_start = time.monotonic()
        from funasr import AutoModel as auto_model_cls  # local lazy import
        from funasr.utils.postprocess_utils import (
            rich_transcription_postprocess as postprocess_fn,  # local lazy import
        )

        _AUTOMODEL_CLS = auto_model_cls
        _POSTPROCESS_FN = postprocess_fn
        logging.info("funasr lazy import done in %.3fs", time.monotonic() - import_start)


def maybe_postprocess_text(raw_text: str) -> str:
    # Avoid unnecessary rich postprocess pass when there are no special markers.
    if not raw_text:
        return ""
    if "<|" not in raw_text and "/sil" not in raw_text:
        return raw_text
    ensure_funasr_modules_loaded()
    assert _POSTPROCESS_FN is not None
    return _POSTPROCESS_FN(raw_text)


def _detect_app_language() -> str:
    try:
        langs = NSLocale.preferredLanguages() or []
        if langs:
            first = str(langs[0]).lower()
            if first.startswith("zh"):
                return "zh"
    except Exception:
        pass
    return "en"


APP_LANG = _detect_app_language()

I18N = {
    "app_name": {"zh": "FunASR Dictation", "en": "FunASR Dictation"},
    "ok": {"zh": "确定", "en": "OK"},
    "save": {"zh": "保存", "en": "Save"},
    "cancel": {"zh": "取消", "en": "Cancel"},
    "manual": {"zh": "手动", "en": "Manual"},
    "done": {"zh": "完成", "en": "Done"},
    "menu_toggle": {"zh": "开关语音输入", "en": "Toggle Dictation"},
    "menu_use_keyboard": {"zh": "使用键盘触发", "en": "Use Keyboard Trigger"},
    "menu_use_mouse": {"zh": "使用鼠标触发", "en": "Use Mouse Trigger"},
    "menu_set_hotkey": {"zh": "设置键盘快捷键", "en": "Set Keyboard Hotkey"},
    "menu_set_mouse": {"zh": "设置鼠标按键", "en": "Set Mouse Button"},
    "menu_hotkey_settings": {"zh": "快捷键设置", "en": "Hotkey Settings"},
    "menu_model_config": {"zh": "模型参数设置", "en": "Model Config"},
    "menu_update_model": {"zh": "更新模型", "en": "Update Model"},
    "menu_auto_on": {"zh": "应用启动时自动开启听写", "en": "Enable Dictation On App Start"},
    "menu_launch_login": {"zh": "开机自动启动", "en": "Enable Launch At Login"},
    "menu_quit": {"zh": "退出应用", "en": "Quit App"},
    "build_prefix": {"zh": "版本", "en": "Build"},
    "status_prefix": {"zh": "状态", "en": "Status"},
    "trigger_prefix": {"zh": "触发方式", "en": "Trigger"},
    "mode_keyboard": {"zh": "键盘", "en": "keyboard"},
    "mode_mouse": {"zh": "鼠标", "en": "mouse"},
    "status_off": {"zh": "关闭", "en": "OFF"},
    "status_loading": {"zh": "加载中", "en": "LOADING"},
    "status_updating": {"zh": "更新中", "en": "UPDATING"},
    "status_ready": {"zh": "就绪", "en": "READY"},
    "status_recording": {"zh": "录音中", "en": "RECORDING"},
    "status_transcribing": {"zh": "转写中", "en": "TRANSCRIBING"},
    "status_error": {"zh": "错误", "en": "ERROR"},
    "invalid_model_config_title": {"zh": "模型参数无效", "en": "Invalid Model Config"},
    "model_config_title": {"zh": "模型参数设置", "en": "Model Config"},
    "model_config_intro": {
        "zh": "使用易懂选项来调整识别表现（保存后下次录音生效）",
        "en": "Tune dictation behavior with plain-language options (applies from next recording)",
    },
    "model_config_hint": {
        "zh": "推荐：语言=auto，数字/日期规范化=开，长停顿合并=关；专有词写入高频词。",
        "en": "Recommended: language=auto, normalize numbers/dates=ON, merge long pauses=OFF; add domain words in Hot Words.",
    },
    "model_config_field_language": {"zh": "识别语言", "en": "Recognition Language"},
    "model_config_field_sample_rate": {"zh": "采样率 (Hz)", "en": "Sample Rate (Hz)"},
    "model_config_field_sample_rate_help": {
        "zh": "建议 16000；仅在设备不兼容时改为 44100/48000。",
        "en": "Recommended: 16000. Use 44100/48000 only if your mic requires it.",
    },
    "model_config_field_channels": {"zh": "声道数", "en": "Channels"},
    "model_config_field_channels_help": {
        "zh": "建议 1（单声道）；双声道麦克风可设为 2。",
        "en": "Recommended: 1 (mono). Use 2 only for stereo input devices.",
    },
    "model_config_field_paste_delay": {"zh": "粘贴延迟 (ms)", "en": "Paste Delay (ms)"},
    "model_config_field_paste_delay_help": {
        "zh": "建议 20-40；若偶发粘贴失败可提高到 60。",
        "en": "Recommended: 20-40. If paste occasionally fails, try up to 60.",
    },
    "model_config_field_hotwords": {"zh": "高频词（逗号或换行分隔）", "en": "Hot Words (comma/newline separated)"},
    "model_config_field_hotwords_help": {
        "zh": "用于专有词/人名/产品名，建议 5-50 个。",
        "en": "For names, brands, and jargon. Recommended: 5-50 terms.",
    },
    "model_config_opt_beep": {"zh": "录音提示音（开始/结束）", "en": "Record Beeps (start/stop)"},
    "model_config_opt_itn": {"zh": "数字与日期规范化（推荐开启）", "en": "Normalize Numbers/Dates (recommended ON)"},
    "model_config_opt_itn_desc": {
        "zh": "开启：文本更规整；关闭：更接近原始口语。",
        "en": "ON: cleaner formatting. OFF: closer to raw spoken text.",
    },
    "model_config_opt_merge_vad": {"zh": "合并长停顿片段（速度优先）", "en": "Merge Long-Pause Segments (speed-first)"},
    "model_config_opt_merge_vad_desc": {
        "zh": "开启：长语音可能更快，但断句可能更粗；关闭：断句通常更自然。",
        "en": "ON: can be faster for long audio, but punctuation may be rougher. OFF: usually better sentence breaks.",
    },
    "model_config_opt_remove_emoji": {"zh": "过滤表情符号", "en": "Remove Emoji Symbols"},
    "manual_hotkey_prompt": {
        "zh": "手动输入快捷键（例如 <ctrl>+<alt>+<space> 或 f8）",
        "en": "Manually enter a hotkey (e.g. <ctrl>+<alt>+<space> or f8).",
    },
    "hotkey_invalid": {
        "zh": "快捷键格式无效或当前版本不支持该按键。",
        "en": "Invalid hotkey format or unsupported key token.",
    },
    "manual_mouse_prompt": {
        "zh": "手动输入鼠标触发键（例如 x1、x2、middle、button8）。\n不支持 left/right。",
        "en": "Manually enter mouse trigger (e.g. x1, x2, middle, button8).\nleft/right are not supported.",
    },
    "choose_mode_prompt_hotkey": {
        "zh": "选择设置方式：\n1) 开始识别：8 秒内按下想设置的快捷键。\n2) 手动输入：直接输入快捷键文本。",
        "en": "Choose setup mode:\n1) Start Capture: press your hotkey within 8 seconds.\n2) Manual Input: type the hotkey text directly.",
    },
    "choose_mode_prompt_mouse": {
        "zh": "选择设置方式：\n1) 开始识别：20 秒内按下目标鼠标按键。\n2) 手动输入：直接输入 middle/x1/x2/buttonN。",
        "en": "Choose setup mode:\n1) Start Capture: press your mouse button within 20 seconds.\n2) Manual Input: type middle/x1/x2/buttonN directly.",
    },
    "btn_start_capture": {"zh": "开始识别", "en": "Start Capture"},
    "btn_manual_input": {"zh": "手动输入", "en": "Manual Input"},
    "btn_retry_capture": {"zh": "重试识别", "en": "Retry Capture"},
    "capture_window_hint": {
        "zh": "正在识别，请按下目标按键...",
        "en": "Capturing... press the target key/button now.",
    },
    "capture_hotkey_progress": {"zh": "正在识别快捷键（最多 8 秒）", "en": "Capturing keyboard hotkey (up to 8s)"},
    "capture_mouse_progress": {"zh": "正在识别鼠标按键（最多 20 秒）", "en": "Capturing mouse button (up to 20s)"},
    "capture_mouse_hid_progress": {"zh": "尝试备用识别（HID 事件，最多 8 秒）", "en": "Fallback capture (HID event tap, up to 8s)"},
    "capture_mouse_pynput_progress": {"zh": "尝试备用识别（pynput，最多 12 秒）", "en": "Fallback capture (pynput, up to 12s)"},
    "notify_hotkey_subtitle": {"zh": "8 秒内监听中", "en": "Listening for 8 seconds"},
    "notify_hotkey_message": {"zh": "请按下目标快捷键组合，按 Esc 可取消。", "en": "Press your desired key combination now. Esc cancels capture."},
    "notify_mouse_subtitle": {"zh": "20 秒内监听中", "en": "Listening for 20 seconds"},
    "notify_mouse_message": {"zh": "请按下目标鼠标按键（左键/右键会忽略）。", "en": "Click your target mouse button now. Left/right are ignored."},
    "notify_fallback_subtitle": {"zh": "备用识别", "en": "Fallback capture"},
    "notify_fallback_hid": {"zh": "正在尝试 HID 事件识别...", "en": "Trying HID event tap fallback..."},
    "notify_fallback_pynput": {"zh": "正在尝试 pynput 识别...", "en": "Trying pynput mouse listener fallback..."},
    "hotkey_captured_edit": {"zh": "已识别到快捷键: {value}\n可直接保存或手动修改。", "en": "Captured hotkey: {value}\nYou can save or edit it."},
    "mouse_captured_edit": {"zh": "已识别到鼠标按键: {value}\n可直接保存或手动修改。", "en": "Captured mouse button: {value}\nYou can save or edit it."},
    "capture_failed": {"zh": "自动识别失败：{error}", "en": "Auto capture failed: {error}"},
    "capture_timeout_hotkey": {"zh": "8 秒内未识别到快捷键。", "en": "No hotkey captured within 8 seconds."},
    "capture_timeout_mouse": {"zh": "未识别到可用鼠标按键（左键/右键会被忽略）。", "en": "No usable mouse button captured (left/right are ignored)."},
    "retry_or_manual": {"zh": "你可以重试识别，或手动输入。", "en": "You can retry capture or switch to manual input."},
    "hotkey_settings_summary": {
        "zh": "当前触发方式：{mode}\n键盘快捷键：{hotkey}\n鼠标按键：{mouse}\n\n建议：先设置按键，再切换触发方式。",
        "en": "Current trigger mode: {mode}\nKeyboard hotkey: {hotkey}\nMouse button: {mouse}\n\nTip: set keys first, then choose trigger mode.",
    },
    "hotkey_settings_btn_use_keyboard": {"zh": "启用键盘触发", "en": "Use Keyboard Trigger"},
    "hotkey_settings_btn_use_mouse": {"zh": "启用鼠标触发", "en": "Use Mouse Trigger"},
    "hotkey_settings_btn_set_keyboard": {"zh": "设置键盘快捷键", "en": "Set Keyboard Hotkey"},
    "hotkey_settings_btn_set_mouse": {"zh": "设置鼠标按键", "en": "Set Mouse Button"},
    "mouse_invalid": {
        "zh": "鼠标按键格式无效。支持 middle、x1、x2、buttonN（N>=2，且不含 0/1）。",
        "en": "Invalid mouse button format. Supported: middle, x1, x2, buttonN (N>=2; excluding 0/1).",
    },
    "mouse_keyboard_mapped_hint": {
        "zh": "未检测到可用鼠标按钮，但检测到按键组合：{value}\n这通常表示鼠标驱动已把侧键映射为键盘快捷键。\n你可以：\n1) 在 Logi Options+ 把该按键改为 Generic Button；或\n2) 在“快捷键设置”里设置该键盘组合。",
        "en": "No usable mouse button was captured, but keyboard combo detected: {value}\nThis usually means your mouse driver mapped side buttons to keyboard shortcuts.\nYou can:\n1) Set that button to Generic Button in Logi Options+; or\n2) Configure this combo in Hotkey Settings.",
    },
    "no_key_captured": {"zh": "未捕获到快捷键。", "en": "No key captured."},
    "hotkey_saved": {"zh": "已设置快捷键: {value}", "en": "Keyboard hotkey saved: {value}"},
    "hotkey_set_failed": {"zh": "设置键盘快捷键失败: {error}", "en": "Set Keyboard Hotkey failed: {error}"},
    "no_mouse_captured": {"zh": "未捕获到鼠标按键。", "en": "No mouse button captured."},
    "mouse_saved": {"zh": "已设置鼠标按键: {value}", "en": "Mouse trigger saved: {value}"},
    "mouse_set_failed": {"zh": "设置鼠标按键失败: {error}", "en": "Set Mouse Button failed: {error}"},
    "model_config_saved": {"zh": "Model Config 已保存。新参数将从下一次录音开始生效。", "en": "Model Config saved. New parameters will apply from the next recording."},
    "model_config_save_failed": {"zh": "Model Config 保存失败: {error}", "en": "Failed to save Model Config: {error}"},
    "update_in_progress": {"zh": "模型更新已在进行中。", "en": "Model update is already running."},
    "update_timeout_failed": {"zh": "模型更新失败：下载或加载超时，请稍后重试。", "en": "Model update failed: download/load timed out. Please retry later."},
    "update_completed": {"zh": "模型更新完成。", "en": "Model update completed."},
    "update_failed": {"zh": "模型更新失败: {error}", "en": "Model update failed: {error}"},
    "autostart_migrate_failed": {
        "zh": "检测到旧版开机自启动配置，自动迁移失败。请在菜单中关闭再开启一次“开机自动启动”。",
        "en": "Legacy launch-at-login config detected but migration failed. Please toggle Enable Launch At Login off and on once.",
    },
    "permission_event_tap_failed": {
        "zh": "无法创建键盘监听（event tap）。这通常是权限归属问题。\n请按以下步骤重试：\n1) ./remove_launcher.sh\n2) ./create_launcher.sh\n3) 双击 FunASR Dictation.app 启动一次（不要用终端）\n4) 在系统设置中给 “FunASR Dictation” 勾选 Accessibility 和 Input Monitoring。\n当前 Python: {python}",
        "en": "Failed to create keyboard event tap. This is usually a permission-attribution issue.\nPlease retry with:\n1) ./remove_launcher.sh\n2) ./create_launcher.sh\n3) Launch once by double-clicking FunASR Dictation.app (not Terminal)\n4) Re-enable Accessibility and Input Monitoring for \"FunASR Dictation\" in System Settings.\nCurrent Python: {python}",
    },
    "permission_hint": {
        "zh": "监听权限可能未生效。请从桌面或 Applications 双击 FunASR Dictation.app 启动，并在 系统设置 -> 隐私与安全性 -> 输入监控 / 辅助功能 中勾选对应条目后重启应用。若列表里没有 FunASR Dictation，请同时检查并放行 Python。",
        "en": "Input-monitoring permissions may not be effective. Launch from FunASR Dictation.app (Desktop/Applications), then enable entries under System Settings -> Privacy & Security -> Input Monitoring / Accessibility and restart. If FunASR Dictation is not listed, also allow Python.",
    },
    "silent_audio_hint": {
        "zh": "检测到录音为静音（音量全为 0）。请检查：\n1) 系统设置 -> 隐私与安全性 -> 麦克风，是否允许 FunASR Dictation / Python\n2) 系统设置 -> 声音 -> 输入，是否选中了正确麦克风\n3) 麦克风本身是否被静音或被其他软件占用",
        "en": "Captured audio is fully silent (all zeros). Please check:\n1) System Settings -> Privacy & Security -> Microphone: allow FunASR Dictation / Python\n2) System Settings -> Sound -> Input: select the correct microphone\n3) The microphone is not muted or exclusively occupied by another app",
    },
    "launch_login_update_failed": {"zh": "更新开机自动启动失败: {error}", "en": "Failed to update Launch At Login: {error}"},
    "already_running_hint": {
        "zh": "FunASR Dictation 已在菜单栏运行。",
        "en": "FunASR Dictation is already running in the menu bar.",
    },
}


def tr(key: str, **kwargs) -> str:
    item = I18N.get(key)
    if not item:
        text = key
    else:
        text = item.get(APP_LANG) or item.get("en") or key
    return text.format(**kwargs) if kwargs else text


def localized_status(status: str) -> str:
    return tr(f"status_{status.lower()}")


FUNASR_LANGUAGE_MAP = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "yue": "粤语",
    "ko": "韩文",
}


def resolve_funasr_language(value: str) -> Optional[str]:
    raw = (value or "").strip().lower()
    if raw in {"", "auto", "nospeech"}:
        return None
    return FUNASR_LANGUAGE_MAP.get(raw, raw)


def ensure_funasr_runtime_imports() -> None:
    runtime_dir = str(FUNASR_RUNTIME_DIR.resolve())
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)


def _applescript_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _rounded_icon_image(image: NSImage, ratio: float = 0.22) -> NSImage:
    size = image.size()
    w = float(size.width)
    h = float(size.height)
    if w <= 1 or h <= 1:
        return image
    rect = NSMakeRect(0, 0, w, h)
    rounded = NSImage.alloc().initWithSize_(size)
    rounded.lockFocus()
    try:
        radius = min(w, h) * ratio
        clip = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius)
        clip.addClip()
        image.drawInRect_(rect)
    finally:
        rounded.unlockFocus()
    return rounded


def _app_icon_image(*, rounded: bool = False) -> Optional[NSImage]:
    global _APP_ICON_CACHE, _APP_ICON_ROUNDED_CACHE
    if _APP_ICON_CACHE is None:
        icon_path = APP_ICON if Path(APP_ICON).exists() else MENU_ICON
        if Path(icon_path).exists():
            icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
            if icon is not None:
                _APP_ICON_CACHE = icon
    if _APP_ICON_CACHE is None:
        return None
    if not rounded:
        return _APP_ICON_CACHE
    if _APP_ICON_ROUNDED_CACHE is None:
        try:
            _APP_ICON_ROUNDED_CACHE = _rounded_icon_image(_APP_ICON_CACHE)
        except Exception as exc:
            logging.warning("rounded icon render failed: %s", exc)
            _APP_ICON_ROUNDED_CACHE = _APP_ICON_CACHE
    return _APP_ICON_ROUNDED_CACHE


def ui_alert_native(message: str, title: Optional[str] = None) -> None:
    app = NSApplication.sharedApplication()
    app.activateIgnoringOtherApps_(True)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(title or tr("app_name"))
    alert.setInformativeText_(message)
    icon = _app_icon_image(rounded=True)
    if icon is not None:
        alert.setIcon_(icon)
    alert.addButtonWithTitle_(tr("ok"))
    alert.runModal()


def ui_prompt_text_native(
    message: str,
    title: str,
    default_text: str = "",
    ok_text: str = "Save",
    cancel_text: str = "Cancel",
) -> Optional[str]:
    app = NSApplication.sharedApplication()
    app.activateIgnoringOtherApps_(True)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setInformativeText_(message)
    icon = _app_icon_image(rounded=True)
    if icon is not None:
        alert.setIcon_(icon)
    alert.addButtonWithTitle_(ok_text)
    alert.addButtonWithTitle_(cancel_text)

    field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 360, 24))
    field.setStringValue_(default_text)
    alert.setAccessoryView_(field)

    resp = alert.runModal()
    if resp != NSAlertFirstButtonReturn:
        return None
    return field.stringValue().strip()


def ui_choice_native(
    *,
    title: str,
    message: str,
    primary_text: str,
    secondary_text: str,
    cancel_text: Optional[str] = None,
) -> str:
    app = NSApplication.sharedApplication()
    app.activateIgnoringOtherApps_(True)
    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setInformativeText_(message)
    icon = _app_icon_image(rounded=True)
    if icon is not None:
        alert.setIcon_(icon)
    alert.addButtonWithTitle_(primary_text)
    alert.addButtonWithTitle_(secondary_text)
    alert.addButtonWithTitle_(cancel_text or tr("cancel"))
    resp = alert.runModal()
    if resp == NSAlertFirstButtonReturn:
        return "primary"
    if resp == NSAlertFirstButtonReturn + 1:
        return "secondary"
    return "cancel"


def ui_hotkey_settings_action(settings: "UISettings") -> str:
    app = NSApplication.sharedApplication()
    app.activateIgnoringOtherApps_(True)
    mode = tr("mode_mouse") if settings.trigger_mode == "mouse" else tr("mode_keyboard")
    hotkey = normalize_keyboard_hotkey(settings.keyboard_hotkey)
    mouse_value = normalize_mouse_button(settings.mouse_button) or settings.mouse_button
    alert = NSAlert.alloc().init()
    # Hide NSAlert default app icon area (which can show Python icon) and
    # render our own centered header/icon in accessory view.
    blank_icon = NSImage.alloc().initWithSize_(NSMakeSize(1.0, 1.0))
    alert.setIcon_(blank_icon)
    alert.setMessageText_("")
    alert.setInformativeText_("")

    summary = tr(
        "hotkey_settings_summary",
        mode=mode,
        hotkey=hotkey,
        mouse=mouse_value,
    )
    panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 360, 178))

    icon = _app_icon_image(rounded=True)
    if icon is not None:
        icon_size = 52
        icon_x = (360 - icon_size) / 2.0
        icon_view = NSImageView.alloc().initWithFrame_(NSMakeRect(icon_x, 114, icon_size, icon_size))
        icon_view.setImage_(icon)
        panel.addSubview_(icon_view)

    title = NSTextField.alloc().initWithFrame_(NSMakeRect(10, 88, 340, 24))
    title.setEditable_(False)
    title.setBezeled_(False)
    title.setDrawsBackground_(False)
    title.setSelectable_(False)
    title.setAlignment_(NSTextAlignmentCenter)
    title.setStringValue_(tr("menu_hotkey_settings"))
    panel.addSubview_(title)

    y = 60
    for line in summary.splitlines():
        if not line.strip():
            y -= 4
            continue
        text = NSTextField.alloc().initWithFrame_(NSMakeRect(18, y, 324, 20))
        text.setEditable_(False)
        text.setBezeled_(False)
        text.setDrawsBackground_(False)
        text.setSelectable_(False)
        text.setStringValue_(line)
        panel.addSubview_(text)
        y -= 20

    alert.setAccessoryView_(panel)
    alert.addButtonWithTitle_(tr("hotkey_settings_btn_set_keyboard"))
    alert.addButtonWithTitle_(tr("hotkey_settings_btn_set_mouse"))
    alert.addButtonWithTitle_(tr("hotkey_settings_btn_use_keyboard"))
    alert.addButtonWithTitle_(tr("hotkey_settings_btn_use_mouse"))
    alert.addButtonWithTitle_(tr("done"))
    # Make "Done" the default (blue) button instead of the first action button.
    try:
        buttons = list(alert.buttons())
        if len(buttons) >= 5:
            for idx in range(4):
                buttons[idx].setKeyEquivalent_("")
            buttons[4].setKeyEquivalent_("\r")
    except Exception:
        pass
    resp = alert.runModal()
    if resp == NSAlertFirstButtonReturn:
        return "set_keyboard"
    if resp == NSAlertFirstButtonReturn + 1:
        return "set_mouse"
    if resp == NSAlertFirstButtonReturn + 2:
        return "use_keyboard"
    if resp == NSAlertFirstButtonReturn + 3:
        return "use_mouse"
    return "done"


def run_with_ui_responsiveness(task_name: str, fn: Callable[[], object]):
    done = threading.Event()
    holder = {"value": None, "error": None, "elapsed": 0.0}

    def worker():
        started = time.monotonic()
        try:
            holder["value"] = fn()
        except Exception as exc:
            holder["error"] = exc
        finally:
            holder["elapsed"] = time.monotonic() - started
            done.set()

    threading.Thread(target=worker, daemon=True).start()
    run_loop = NSRunLoop.currentRunLoop()
    while not done.wait(0.03):
        run_loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.01))

    logging.info("%s finished in %.3fs", task_name, holder["elapsed"])
    if holder["error"] is not None:
        raise holder["error"]
    return holder["value"]


def _show_capture_progress_window(title: str, message: str):
    app = NSApplication.sharedApplication()
    app.activateIgnoringOtherApps_(True)
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 420, 150),
        NSWindowStyleMaskTitled,
        NSBackingStoreBuffered,
        False,
    )
    window.setTitle_(title)
    window.center()
    window.setReleasedWhenClosed_(False)

    content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 420, 150))
    window.setContentView_(content)

    icon = _app_icon_image(rounded=True)
    if icon is not None:
        icon_view = NSImageView.alloc().initWithFrame_(NSMakeRect(20, 84, 46, 46))
        icon_view.setImage_(icon)
        content.addSubview_(icon_view)

    msg = NSTextField.alloc().initWithFrame_(NSMakeRect(80, 88, 320, 44))
    msg.setEditable_(False)
    msg.setBezeled_(False)
    msg.setDrawsBackground_(False)
    msg.setSelectable_(False)
    msg.setStringValue_(message)
    content.addSubview_(msg)

    spinner = NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(80, 52, 24, 24))
    spinner.setIndeterminate_(True)
    try:
        spinner.setStyle_(NSProgressIndicatorStyleSpinning)
    except Exception:
        pass
    spinner.startAnimation_(None)
    content.addSubview_(spinner)

    hint = NSTextField.alloc().initWithFrame_(NSMakeRect(112, 54, 288, 20))
    hint.setEditable_(False)
    hint.setBezeled_(False)
    hint.setDrawsBackground_(False)
    hint.setSelectable_(False)
    hint.setStringValue_(tr("capture_window_hint"))
    content.addSubview_(hint)

    window.makeKeyAndOrderFront_(None)
    return window


def run_with_progress_window(
    task_name: str,
    progress_title: str,
    progress_message: str,
    fn: Callable[[], object],
):
    window = None
    try:
        window = _show_capture_progress_window(progress_title, progress_message)
    except Exception as exc:
        logging.warning("show progress window failed: %s", exc)
    try:
        return run_with_ui_responsiveness(task_name, fn)
    finally:
        if window is not None:
            try:
                window.orderOut_(None)
                window.close()
            except Exception:
                pass


def notify_user(title: str, subtitle: str, message: str) -> None:
    try:
        rumps.notification(title, subtitle, message)
    except Exception as exc:
        logging.debug("notification failed: %s", exc)


def ui_alert(message: str, title: Optional[str] = None) -> None:
    icon_clause = ""
    if Path(APP_ICON).exists():
        icon_clause = f' with icon POSIX file "{_applescript_escape(APP_ICON)}"'
    script = (
        f'display dialog "{_applescript_escape(message)}" '
        f'with title "{_applescript_escape(title or tr("app_name"))}" '
        f'buttons {{"OK"}} default button "OK"{icon_clause}'
    )
    subprocess.run(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def ui_notify(message: str, title: Optional[str] = None) -> None:
    script = (
        f'display notification "{_applescript_escape(message)}" '
        f'with title "{_applescript_escape(title or tr("app_name"))}"'
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
    ok_text: Optional[str] = None,
    cancel_text: Optional[str] = None,
) -> Optional[str]:
    ok = ok_text or tr("save")
    cancel = cancel_text or tr("cancel")
    icon_clause = ""
    if Path(APP_ICON).exists():
        icon_clause = f' with icon POSIX file "{_applescript_escape(APP_ICON)}"'
    script = (
        f'display dialog "{_applescript_escape(message)}" '
        f'with title "{_applescript_escape(title)}" '
        f'default answer "{_applescript_escape(default_text)}" '
        f'buttons {{"{_applescript_escape(cancel)}","{_applescript_escape(ok)}"}} '
        f'default button "{_applescript_escape(ok)}" '
        f'cancel button "{_applescript_escape(cancel)}"{icon_clause}\n'
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
    paste_delay_ms: int = 20
    enable_beep: bool = True
    use_itn: bool = True
    batch_size_s: int = 0
    merge_vad: bool = False
    remove_emoji: bool = True
    hotwords: str = ""


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
        paste_delay_ms=int(data.get("paste_delay_ms", 20)),
        enable_beep=bool(data.get("enable_beep", True)),
        use_itn=bool(data.get("use_itn", True)),
        # This runtime currently requires batch_size_s=0 for VAD path compatibility.
        batch_size_s=0,
        merge_vad=bool(data.get("merge_vad", False)),
        remove_emoji=bool(data.get("remove_emoji", True)),
        hotwords=str(data.get("hotwords", "")),
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
        "# Fun-ASR language: auto, zh, en, ja\n"
        "# For mixed zh/en dictation, keep auto.\n"
        f'language = "{language}"\n\n'
        "# Audio configuration\n"
        f"sample_rate = {int(config.sample_rate)}\n"
        f"channels = {int(config.channels)}\n\n"
        "# Paste behavior (actual runtime clamps this into 15~60ms)\n"
        f"paste_delay_ms = {int(config.paste_delay_ms)}\n\n"
        "# Enable system sound when start/stop recording\n"
        f"enable_beep = {b(bool(config.enable_beep))}\n\n"
        "# Fun-ASR inference options\n"
        "# ITN: normalize numbers/date etc., may improve readability in some cases.\n"
        f"use_itn = {b(bool(config.use_itn))}\n"
        "# NOTE: this runtime currently requires batch_size_s=0 for compatibility.\n"
        "# Kept as a fixed internal value (not exposed in Model Config UI).\n"
        "batch_size_s = 0\n"
        "# false=keep VAD segments, true=merge segments for potentially faster decoding.\n"
        f"merge_vad = {b(bool(config.merge_vad))}\n\n"
        '# Optional comma-separated domain terms, e.g. "OpenAI, GitHub, LaunchAgent"\n'
        f'hotwords = "{config.hotwords.replace(chr(34), "").strip()}"\n\n'
        "# Remove emoji symbols from final pasted text.\n"
        f"remove_emoji = {b(bool(config.remove_emoji))}\n"
    )
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def ui_edit_model_config(current: CoreConfig) -> Optional[CoreConfig]:
    def parse_int(raw: str, name: str, min_value: int, max_value: int) -> int:
        try:
            value = int(raw.strip())
        except Exception as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if value < min_value or value > max_value:
            raise ValueError(f"{name} must be in [{min_value}, {max_value}]")
        return value

    state = {
        "language": current.language,
        "sample_rate": str(current.sample_rate),
        "channels": str(current.channels),
        "paste_delay_ms": str(current.paste_delay_ms),
        "hotwords": current.hotwords,
        "enable_beep": bool(current.enable_beep),
        "use_itn": bool(current.use_itn),
        "merge_vad": bool(current.merge_vad),
        "remove_emoji": bool(current.remove_emoji),
    }

    def normalize_hotwords(raw: str) -> str:
        tokens = [token.strip() for token in re.split(r"[,\n\r;，]+", raw or "") if token.strip()]
        deduped: List[str] = []
        seen = set()
        for token in tokens:
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(token)
        return ", ".join(deduped)

    while True:
        app = NSApplication.sharedApplication()
        app.activateIgnoringOtherApps_(True)

        alert = NSAlert.alloc().init()
        alert.setMessageText_(tr("model_config_title"))
        alert.setInformativeText_(tr("model_config_intro"))
        icon = _app_icon_image(rounded=True)
        if icon is not None:
            alert.setIcon_(icon)
        alert.addButtonWithTitle_(tr("save"))
        alert.addButtonWithTitle_(tr("cancel"))

        panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 450, 452))

        def make_label(y: float, text: str):
            label = NSTextField.alloc().initWithFrame_(NSMakeRect(10, y, 160, 22))
            label.setEditable_(False)
            label.setBezeled_(False)
            label.setDrawsBackground_(False)
            label.setSelectable_(False)
            label.setStringValue_(text)
            panel.addSubview_(label)
            return label

        def make_input(y: float, value: str):
            field = NSTextField.alloc().initWithFrame_(NSMakeRect(170, y, 270, 24))
            field.setStringValue_(value)
            panel.addSubview_(field)
            return field

        def make_check(y: float, text: str, value: bool):
            box = NSButton.alloc().initWithFrame_(NSMakeRect(10, y, 430, 22))
            box.setButtonType_(NSSwitchButton)
            box.setTitle_(text)
            box.setState_(NSControlStateValueOn if value else 0)
            panel.addSubview_(box)
            return box

        def make_plain_text(y: float, text: str):
            label = NSTextField.alloc().initWithFrame_(NSMakeRect(10, y, 430, 18))
            label.setEditable_(False)
            label.setBezeled_(False)
            label.setDrawsBackground_(False)
            label.setSelectable_(False)
            label.setStringValue_(text)
            panel.addSubview_(label)
            return label

        def make_multiline_input(y: float, value: str):
            scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(170, y, 270, 108))
            scroll.setBorderType_(NSBezelBorder)
            scroll.setHasVerticalScroller_(True)
            scroll.setHasHorizontalScroller_(False)
            text_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 270, 108))
            text_view.setString_((value or "").replace(", ", "\n"))
            scroll.setDocumentView_(text_view)
            panel.addSubview_(scroll)
            return text_view

        make_label(426, tr("model_config_field_language"))
        language_field = make_input(424, state["language"])
        make_label(394, tr("model_config_field_sample_rate"))
        sample_rate_field = make_input(392, state["sample_rate"])
        make_plain_text(374, tr("model_config_field_sample_rate_help"))
        make_label(348, tr("model_config_field_channels"))
        channels_field = make_input(346, state["channels"])
        make_plain_text(328, tr("model_config_field_channels_help"))
        make_label(302, tr("model_config_field_paste_delay"))
        paste_delay_field = make_input(300, state["paste_delay_ms"])
        make_plain_text(282, tr("model_config_field_paste_delay_help"))

        enable_beep_box = make_check(264, tr("model_config_opt_beep"), state["enable_beep"])
        use_itn_box = make_check(238, tr("model_config_opt_itn"), state["use_itn"])
        make_plain_text(220, tr("model_config_opt_itn_desc"))
        merge_vad_box = make_check(196, tr("model_config_opt_merge_vad"), state["merge_vad"])
        make_plain_text(178, tr("model_config_opt_merge_vad_desc"))
        remove_emoji_box = make_check(164, tr("model_config_opt_remove_emoji"), state["remove_emoji"])

        make_label(136, tr("model_config_field_hotwords"))
        make_plain_text(118, tr("model_config_field_hotwords_help"))
        hotwords_field = make_multiline_input(8, state["hotwords"])

        alert.setAccessoryView_(panel)
        resp = alert.runModal()
        if resp != NSAlertFirstButtonReturn:
            logging.info("ui_edit_model_config: canceled")
            return None

        state["language"] = language_field.stringValue().strip().lower()
        state["sample_rate"] = sample_rate_field.stringValue().strip()
        state["channels"] = channels_field.stringValue().strip()
        state["paste_delay_ms"] = paste_delay_field.stringValue().strip()
        state["hotwords"] = normalize_hotwords(str(hotwords_field.string()))
        state["enable_beep"] = bool(enable_beep_box.state() == NSControlStateValueOn)
        state["use_itn"] = bool(use_itn_box.state() == NSControlStateValueOn)
        state["merge_vad"] = bool(merge_vad_box.state() == NSControlStateValueOn)
        state["remove_emoji"] = bool(remove_emoji_box.state() == NSControlStateValueOn)

        try:
            if not state["language"]:
                raise ValueError("language cannot be empty")
            return CoreConfig(
                language=state["language"],
                sample_rate=parse_int(state["sample_rate"], "sample_rate", 8000, 48000),
                channels=parse_int(state["channels"], "channels", 1, 2),
                paste_delay_ms=parse_int(state["paste_delay_ms"], "paste_delay_ms", 0, 1000),
                enable_beep=state["enable_beep"],
                use_itn=state["use_itn"],
                batch_size_s=0,
                merge_vad=state["merge_vad"],
                remove_emoji=state["remove_emoji"],
                hotwords=state["hotwords"],
            )
        except Exception as exc:
            logging.warning("ui_edit_model_config invalid: %s", exc)
            ui_alert_native(str(exc), title=tr("invalid_model_config_title"))


def load_ui_settings() -> UISettings:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not UI_SETTINGS_PATH.exists() and LEGACY_UI_SETTINGS_PATH.exists():
        try:
            shutil.copy2(LEGACY_UI_SETTINGS_PATH, UI_SETTINGS_PATH)
            logging.info(
                "migrated ui settings from legacy path: %s -> %s",
                LEGACY_UI_SETTINGS_PATH,
                UI_SETTINGS_PATH,
            )
        except Exception as exc:
            logging.warning("failed to migrate legacy ui settings: %s", exc)

    if not UI_SETTINGS_PATH.exists():
        settings = UISettings()
        save_ui_settings(settings)
        return settings

    try:
        with open(UI_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logging.warning("load_ui_settings: invalid json, reset to defaults: %s", exc)
        try:
            bad = UI_SETTINGS_PATH.with_suffix(".json.broken")
            if bad.exists():
                bad.unlink()
            UI_SETTINGS_PATH.replace(bad)
        except Exception:
            pass
        settings = UISettings()
        save_ui_settings(settings)
        return settings

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
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = asdict(settings)
    tmp_path = UI_SETTINGS_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, UI_SETTINGS_PATH)

    # Best-effort mirror for backward compatibility with older builds.
    try:
        with open(LEGACY_UI_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


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


def ensure_listen_permission(request_prompt: bool = False) -> bool:
    ok = bool(Quartz.CGPreflightListenEventAccess())
    if ok:
        return True

    if request_prompt:
        try:
            Quartz.CGRequestListenEventAccess()
        except Exception:
            pass

    ok = bool(Quartz.CGPreflightListenEventAccess())
    if not ok:
        logging.warning("listen permission missing: Input Monitoring/Accessibility not granted")
    return ok


def log_runtime_context() -> None:
    try:
        pid = os.getpid()
        ppid = os.getppid()
        parent_cmd = ""
        try:
            proc = subprocess.run(
                ["ps", "-p", str(ppid), "-o", "command="],
                capture_output=True,
                text=True,
                check=False,
            )
            parent_cmd = (proc.stdout or "").strip()
        except Exception:
            parent_cmd = ""
        bundle_id = ""
        try:
            bundle = NSBundle.mainBundle()
            if bundle is not None:
                bundle_id = str(bundle.bundleIdentifier() or "")
        except Exception:
            bundle_id = ""
        logging.info(
            "runtime context pid=%s ppid=%s exec=%s parent=%s bundle_id=%s",
            pid,
            ppid,
            sys.executable,
            parent_cmd,
            bundle_id,
        )
    except Exception as exc:
        logging.warning("runtime context logging failed: %s", exc)


def _effective_autostart_plist() -> Path:
    if AUTOSTART_PLIST.exists():
        return AUTOSTART_PLIST
    if LEGACY_AUTOSTART_PLIST.exists():
        return LEGACY_AUTOSTART_PLIST
    return AUTOSTART_PLIST


def is_os_autostart_enabled() -> bool:
    return AUTOSTART_PLIST.exists() or LEGACY_AUTOSTART_PLIST.exists()


def is_os_autostart_legacy() -> bool:
    plist = _effective_autostart_plist()
    if not plist.exists():
        return False
    if plist == LEGACY_AUTOSTART_PLIST:
        return True
    try:
        content = plist.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return str(AUTOSTART_RUNNER) not in content


def is_os_autostart_runner_outdated() -> bool:
    if not AUTOSTART_RUNNER.exists():
        return False
    try:
        content = AUTOSTART_RUNNER.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    version_marker = f"RUNNER_VERSION={AUTOSTART_RUNNER_VERSION}"
    if version_marker not in content:
        return True
    app_dir_marker = f'APP_DIR="{APP_DIR}"'
    if app_dir_marker not in content:
        return True
    launcher_idx = content.find('if [[ -d "$LAUNCHER_APP" ]]; then')
    script_idx = content.find('if [[ -x "$START_SCRIPT" ]]; then')
    if launcher_idx != -1 and script_idx != -1 and launcher_idx < script_idx:
        return True
    # Old runner pattern: start script is executed directly and fallback launcher is never reached on failure.
    if 'exec /bin/bash "$START_SCRIPT"' in content and "fallback to launcher app" not in content:
        return True
    return False


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
    text = ui_prompt_text_native(
        message=tr("manual_hotkey_prompt"),
        title=f'{tr("menu_set_hotkey")} ({tr("manual")})',
        default_text=current_value,
        ok_text=tr("save"),
        cancel_text=tr("cancel"),
    )
    if text is None:
        return None
    value = normalize_keyboard_hotkey(text)
    if not is_hotkey_supported(value):
        ui_alert_native(tr("hotkey_invalid"), title=tr("menu_set_hotkey"))
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
    text = ui_prompt_text_native(
        message=tr("manual_mouse_prompt"),
        title=f'{tr("menu_set_mouse")} ({tr("manual")})',
        default_text=current_value,
        ok_text=tr("save"),
        cancel_text=tr("cancel"),
    )
    if text is None:
        return None
    return normalize_mouse_button(text)


def choose_hotkey_with_capture(current_value: str) -> Optional[str]:
    action = ui_choice_native(
        title=tr("menu_set_hotkey"),
        message=tr("choose_mode_prompt_hotkey"),
        primary_text=tr("btn_start_capture"),
        secondary_text=tr("btn_manual_input"),
        cancel_text=tr("cancel"),
    )
    if action == "cancel":
        return None
    if action == "secondary":
        return prompt_hotkey_text_fallback(current_value)

    notify_user(
        tr("menu_set_hotkey"),
        tr("notify_hotkey_subtitle"),
        tr("notify_hotkey_message"),
    )
    captured, err = run_with_progress_window(
        "capture_keyboard_hotkey",
        tr("menu_set_hotkey"),
        tr("capture_hotkey_progress"),
        lambda: capture_keyboard_hotkey(timeout_s=8.0),
    )
    if captured:
        edited = ui_prompt_text_native(
            message=tr("hotkey_captured_edit", value=captured),
            title=tr("menu_set_hotkey"),
            default_text=captured,
            ok_text=tr("save"),
            cancel_text=tr("cancel"),
        )
        if edited is None:
            return None
        value = normalize_keyboard_hotkey(edited)
        if not is_hotkey_supported(value):
            ui_alert_native(tr("hotkey_invalid"), title=tr("menu_set_hotkey"))
            return None
        return value

    retry_action = ui_choice_native(
        title=tr("menu_set_hotkey"),
        message=(tr("capture_failed", error=err) if err else tr("capture_timeout_hotkey"))
        + "\n"
        + tr("retry_or_manual"),
        primary_text=tr("btn_retry_capture"),
        secondary_text=tr("btn_manual_input"),
        cancel_text=tr("cancel"),
    )
    if retry_action == "primary":
        return choose_hotkey_with_capture(current_value)
    if retry_action == "secondary":
        return prompt_hotkey_text_fallback(current_value)
    return None


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
    action = ui_choice_native(
        title=tr("menu_set_mouse"),
        message=tr("choose_mode_prompt_mouse"),
        primary_text=tr("btn_start_capture"),
        secondary_text=tr("btn_manual_input"),
        cancel_text=tr("cancel"),
    )
    if action == "cancel":
        return None
    if action == "secondary":
        return prompt_mouse_text_fallback(current_value)

    notify_user(
        tr("menu_set_mouse"),
        tr("notify_mouse_subtitle"),
        tr("notify_mouse_message"),
    )
    captured, err = run_with_progress_window(
        "capture_mouse_button_primary",
        tr("menu_set_mouse"),
        tr("capture_mouse_progress"),
        lambda: capture_mouse_button(timeout_s=20.0, tap_location=EVENT_TAP_LOCATION),
    )
    if not captured:
        hid_location = getattr(Quartz, "kCGHIDEventTap", None)
        if hid_location is not None:
            notify_user(
                tr("menu_set_mouse"),
                tr("notify_fallback_subtitle"),
                tr("notify_fallback_hid"),
            )
            hid_captured, hid_err = run_with_progress_window(
                "capture_mouse_button_hid",
                tr("menu_set_mouse"),
                tr("capture_mouse_hid_progress"),
                lambda: capture_mouse_button(timeout_s=8.0, tap_location=hid_location),
            )
            if hid_captured:
                captured = hid_captured
                err = None
            elif err is None:
                err = hid_err
    if not captured:
        notify_user(
            tr("menu_set_mouse"),
            tr("notify_fallback_subtitle"),
            tr("notify_fallback_pynput"),
        )
        fallback_captured, fallback_err = run_with_progress_window(
            "capture_mouse_button_pynput",
            tr("menu_set_mouse"),
            tr("capture_mouse_pynput_progress"),
            lambda: capture_mouse_button_pynput(timeout_s=12.0),
        )
        if fallback_captured:
            captured = fallback_captured
            err = None
        elif err is None:
            err = fallback_err
    if captured:
        edited = ui_prompt_text_native(
            message=tr("mouse_captured_edit", value=captured),
            title=tr("menu_set_mouse"),
            default_text=captured,
            ok_text=tr("save"),
            cancel_text=tr("cancel"),
        )
        if edited is None:
            return None
        normalized = normalize_mouse_button(edited)
        if normalized is None:
            ui_alert_native(
                tr("mouse_invalid"),
                title=tr("menu_set_mouse"),
            )
            return None
        return normalized

    kb_value, _ = run_with_ui_responsiveness(
        "capture_keyboard_hotkey_for_mouse_hint",
        lambda: capture_keyboard_hotkey(timeout_s=4.0),
    )
    if kb_value:
        ui_alert_native(
            tr("mouse_keyboard_mapped_hint", value=kb_value),
            title=tr("menu_set_mouse"),
        )

    retry_action = ui_choice_native(
        title=tr("menu_set_mouse"),
        message=(tr("capture_failed", error=err) if err else tr("capture_timeout_mouse"))
        + "\n"
        + tr("retry_or_manual"),
        primary_text=tr("btn_retry_capture"),
        secondary_text=tr("btn_manual_input"),
        cancel_text=tr("cancel"),
    )
    if retry_action == "primary":
        return choose_mouse_button_with_capture(current_value)
    if retry_action == "secondary":
        return prompt_mouse_text_fallback(current_value)
    return None


class DictationEngine:
    def __init__(
        self,
        config: CoreConfig,
        status_cb: Callable[[str], None],
        alert_cb: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.status_cb = status_cb
        self.alert_cb = alert_cb
        self.model = None
        self.model_loading = False
        self.stream = None
        self.frames: List[np.ndarray] = []
        self.lock = threading.Lock()
        self.recording = False
        self.processing = False
        self.shutdown_flag = False
        self.silent_audio_alerted = False

    def _set_status(self, status: str) -> None:
        self.status_cb(status)

    def _emit_alert(self, key: str) -> None:
        if self.alert_cb is None:
            return
        try:
            self.alert_cb(tr(key))
        except Exception as exc:
            logging.warning("emit alert failed key=%s err=%s", key, exc)

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
            load_started = time.monotonic()
            if not FUNASR_REMOTE_CODE_PATH.exists():
                raise RuntimeError(f"Fun-ASR runtime file missing: {FUNASR_REMOTE_CODE_PATH}")
            ensure_funasr_runtime_imports()
            ensure_funasr_modules_loaded()
            assert _AUTOMODEL_CLS is not None
            load_errors = []
            try:
                model = _AUTOMODEL_CLS(
                    model=MODEL_NAME,
                    trust_remote_code=True,
                    remote_code=str(FUNASR_REMOTE_CODE_PATH),
                    vad_model=VAD_MODEL_NAME,
                    vad_kwargs={"max_single_segment_time": 30000},
                    device="cpu",
                    disable_update=True,
                    disable_pbar=True,
                    ncpu=DEFAULT_NCPU,
                )
            except Exception as exc:
                load_errors.append(f"trust_remote_code=True: {exc!r}")
                model = _AUTOMODEL_CLS(
                    model=MODEL_NAME,
                    trust_remote_code=False,
                    vad_model=VAD_MODEL_NAME,
                    vad_kwargs={"max_single_segment_time": 30000},
                    device="cpu",
                    disable_update=True,
                    disable_pbar=True,
                    ncpu=DEFAULT_NCPU,
                )
            with self.lock:
                self.model = model
            logging.info(
                "model runtime ncpu=%d load_elapsed=%.3fs",
                DEFAULT_NCPU,
                time.monotonic() - load_started,
            )
            if load_errors:
                logging.warning("model load fallback used: %s", " | ".join(load_errors))
        except Exception as exc:
            logging.exception("model load failed: %s", exc)
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
        logging.info("paste_text: len=%d preview=%r", len(text), text[:80])
        pyperclip.copy(text)
        # Cap delay so stale configs do not add visible latency.
        delay_ms = min(max(self.config.paste_delay_ms, 15), 60)
        time.sleep(delay_ms / 1000)
        proc = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            logging.warning("paste_text osascript failed rc=%s err=%s", proc.returncode, (proc.stderr or "").strip())
        else:
            logging.info("paste_text done")

    @staticmethod
    def _cleanup_text(text: str, remove_emoji: bool) -> str:
        if remove_emoji:
            text = EMOJI_RE.sub("", text)
        text = text.replace("\u3000", " ")
        text = re.sub(r"\s+", " ", text)
        # Remove unwanted spacing between Chinese characters.
        text = re.sub(rf"(?<=[{CJK_CHAR_CLASS}])\s+(?=[{CJK_CHAR_CLASS}])", "", text)
        # Remove spaces before punctuation.
        text = re.sub(r"\s+([,.;:!?，。！？；：、])", r"\1", text)
        # Remove spaces just inside paired brackets/quotes.
        text = re.sub(r"([（(【\[<{“‘])\s+", r"\1", text)
        text = re.sub(r"\s+([）)】\]>}”’])", r"\1", text)
        text = re.sub(r"\s{2,}", " ", text)
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
            logging.info("start_recording using system default input device: %s", sd.default.device)
            self.stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype="float32",
                callback=self._audio_callback,
            )
            self.stream.start()
        except Exception as exc:
            logging.exception("start_recording stream open failed: %s", exc)
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
            raw_pcm = np.squeeze(audio).astype(np.float32)
            if raw_pcm.ndim == 1 and raw_pcm.size > 0:
                raw_peak = float(np.max(np.abs(raw_pcm)))
                raw_rms = float(np.sqrt(np.mean(np.square(raw_pcm))))
            else:
                raw_peak = 0.0
                raw_rms = 0.0
            pcm = self._trim_silence(audio, self.config.sample_rate)
            if pcm.ndim == 1 and pcm.size > 0:
                trim_peak = float(np.max(np.abs(pcm)))
                trim_rms = float(np.sqrt(np.mean(np.square(pcm))))
            else:
                trim_peak = 0.0
                trim_rms = 0.0
            logging.info(
                "audio_stats raw_len=%d raw_peak=%.5f raw_rms=%.5f trim_len=%d trim_peak=%.5f trim_rms=%.5f",
                int(raw_pcm.size),
                raw_peak,
                raw_rms,
                int(pcm.size if hasattr(pcm, "size") else 0),
                trim_peak,
                trim_rms,
            )
            if raw_peak <= 1e-7 and raw_rms <= 1e-8:
                logging.warning("captured audio is fully silent; skip ASR this turn")
                if not self.silent_audio_alerted:
                    self.silent_audio_alerted = True
                    self._emit_alert("silent_audio_hint")
                return
            lang = resolve_funasr_language(self.config.language)
            gen_kwargs = {
                "input": pcm,
                "cache": {},
                # Fun-ASR-Nano runtime with AutoModel+VAD requires this fixed value.
                "batch_size_s": 0,
                "merge_vad": self.config.merge_vad,
                "audio_fs": self.config.sample_rate,
                "itn": self.config.use_itn,
                "enable_ctc_aux": False,
            }
            if lang is not None:
                gen_kwargs["language"] = lang
            hotwords_raw = (self.config.hotwords or "").strip()
            hotwords = [item.strip() for item in hotwords_raw.split(",") if item.strip()]
            if hotwords:
                gen_kwargs["hotwords"] = hotwords

            try:
                result = self.model.generate(**gen_kwargs)
            except TypeError as exc:
                # Backward compatibility for older runtime signatures.
                logging.warning("generate TypeError, retrying with compatibility kwargs: %s", exc)
                retry_kwargs = dict(gen_kwargs)
                if "itn" in retry_kwargs:
                    retry_kwargs["use_itn"] = retry_kwargs.pop("itn")
                retry_kwargs.pop("hotwords", None)
                retry_kwargs.pop("enable_ctc_aux", None)
                if "audio_fs" in retry_kwargs and "fs" not in retry_kwargs:
                    retry_kwargs["fs"] = retry_kwargs.pop("audio_fs")
                try:
                    result = self.model.generate(**retry_kwargs)
                except TypeError:
                    # Last fallback: drop explicit sample-rate arg for runtimes that
                    # infer it internally.
                    retry_kwargs.pop("fs", None)
                    result = self.model.generate(**retry_kwargs)

            result_list = result
            if isinstance(result, tuple):
                result_list = result[0] if result else []
            if not isinstance(result_list, list):
                logging.warning("unexpected ASR result type: %s", type(result_list))
                result_list = []
            if not result_list:
                logging.info("ASR returned empty result list")
                return
            first = result_list[0] if isinstance(result_list[0], dict) else {}
            raw_text = first.get("text", "") if isinstance(first, dict) else ""
            post_start = time.monotonic()
            text = maybe_postprocess_text(raw_text)
            post_elapsed = time.monotonic() - post_start
            text = self._cleanup_text(text, self.config.remove_emoji)
            if not text:
                logging.info("ASR text empty: raw_text_len=%d", len(raw_text))
            else:
                logging.info(
                    "ASR text ready: raw_len=%d clean_len=%d post_ms=%.3f",
                    len(raw_text),
                    len(text),
                    post_elapsed * 1000.0,
                )
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
        except Exception as exc:
            logging.exception("transcribe failed: %s", exc)
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
            tr("app_name"),
            title="FA○",
            icon=MENU_ICON if Path(MENU_ICON).exists() else None,
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
        self.permission_error_alert_shown = False
        self.last_published_title = ""
        self._status_item_ready_logged = False
        self._status_item_enforce_warned = False
        self._menu_icon_ns: Optional[NSImage] = None

        self.engine = DictationEngine(
            self.core_config,
            self.on_engine_status,
            self._queue_alert,
        )
        self.trigger = TriggerController(self.on_trigger)

        self.status_item = rumps.MenuItem("Status: OFF")
        self.trigger_item = rumps.MenuItem("Trigger: keyboard <ctrl>+<alt>+<space>")
        self.auto_on_item = rumps.MenuItem("Enable Dictation On App Start")
        self.launch_login_item = rumps.MenuItem("Enable Launch At Login")
        self.build_item = rumps.MenuItem(f'{tr("build_prefix")}: {APP_BUILD}')

        self.menu = [
            self.status_item,
            self.trigger_item,
            None,
            "Toggle Dictation",
            "Hotkey Settings",
            "Model Config",
            "Update Model",
            self.auto_on_item,
            self.launch_login_item,
            self.build_item,
            None,
            "Quit App",
        ]
        self.toggle_item = self.menu["Toggle Dictation"]
        self.hotkey_settings_item = self.menu["Hotkey Settings"]
        self.model_config_item = self.menu["Model Config"]
        self.update_model_item = self.menu["Update Model"]
        self.quit_item = self.menu["Quit App"]

        self.refresh_ui_labels()
        self._migrate_autostart_if_needed()
        self.refresh_ui_labels()

        if self.ui_settings.enable_dictation_on_app_start:
            # Show menubar status immediately, then enable in runloop.
            self.on_engine_status("LOADING")
            self.title = "FA…"
            self.status_item.title = f'{tr("status_prefix")}: {localized_status("LOADING")}'
            self.engine.warmup_async()
            self.pending_startup_enable = True

    def _menu_icon_image(self) -> Optional[NSImage]:
        if self._menu_icon_ns is not None:
            return self._menu_icon_ns
        try:
            if not Path(MENU_ICON).exists():
                return None
            icon = NSImage.alloc().initWithContentsOfFile_(MENU_ICON)
            if icon is None:
                return None
            icon.setTemplate_(True)
            icon.setSize_(NSMakeSize(18.0, 18.0))
            self._menu_icon_ns = icon
            return self._menu_icon_ns
        except Exception as exc:
            if not self._status_item_enforce_warned:
                self._status_item_enforce_warned = True
                logging.warning("menu icon load failed: %s", exc)
            return None

    def _ensure_status_item_visible(self) -> None:
        try:
            nsapp = getattr(self, "_nsapp", None)
            nsstatusitem = getattr(nsapp, "nsstatusitem", None)
            if nsstatusitem is None:
                return
            try:
                nsstatusitem.setVisible_(True)
            except Exception:
                pass
            nsstatusitem.setLength_(-1)
            nsstatusitem.setTitle_(self.title or "FA○")
            try:
                nsstatusitem.setHighlightMode_(True)
            except Exception:
                pass
            if nsstatusitem.image() is None:
                icon = self._menu_icon_image()
                if icon is not None:
                    nsstatusitem.setImage_(icon)
            # Some macOS versions only render updates reliably via status button.
            try:
                button = nsstatusitem.button()
            except Exception:
                button = None
            if button is not None:
                button.setTitle_(self.title or "FA○")
                if button.image() is None:
                    icon = self._menu_icon_image()
                    if icon is not None:
                        button.setImage_(icon)
            if not self._status_item_ready_logged:
                self._status_item_ready_logged = True
                hidden = None
                try:
                    app = NSApplication.sharedApplication()
                    hidden = bool(app.isHidden())
                except Exception:
                    hidden = None
                logging.info(
                    "status item active: has_title=%s has_image=%s app_hidden=%s",
                    bool(nsstatusitem.title()),
                    nsstatusitem.image() is not None,
                    hidden,
                )
        except Exception as exc:
            if not self._status_item_enforce_warned:
                self._status_item_enforce_warned = True
                logging.warning("status item enforce failed: %s", exc)

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
            ui_alert_native(msg)

    def _flush_pending_actions(self) -> None:
        if self.pending_reenable:
            self.pending_reenable = False
            self.enable_dictation(show_alert=False, request_prompt=False)
        if self.pending_startup_enable:
            self.pending_startup_enable = False
            self.enable_dictation(show_alert=False, request_prompt=False)

    def on_trigger(self) -> None:
        if not self.dictation_enabled or self.updating_model:
            return
        self.engine.toggle_recording()

    def enable_dictation(self, *, show_alert: bool = True, request_prompt: bool = True) -> None:
        permission_ok = ensure_listen_permission(request_prompt=request_prompt)
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
            self.permission_error_alert_shown = False
        except Exception as exc:
            logging.exception("enable_dictation failed: %s", exc)
            self.dictation_enabled = False
            self.on_engine_status("ERROR")
            if (
                show_alert
                and "Failed to create keyboard event tap" in str(exc)
                and not self.permission_error_alert_shown
            ):
                self.permission_error_alert_shown = True
                ui_alert_native(
                    tr("permission_event_tap_failed", python=sys.executable),
                    title=tr("app_name"),
                )
            if show_alert and not permission_ok and not self.permission_hint_shown:
                self.permission_hint_shown = True
                ui_alert_native(tr("permission_hint"), title=tr("app_name"))

    def disable_dictation(self) -> None:
        self.dictation_enabled = False
        self.trigger.stop()
        self.engine.stop_all()
        self.engine = DictationEngine(
            self.core_config,
            self.on_engine_status,
            self._queue_alert,
        )
        self.on_engine_status("OFF")

    def refresh_ui_labels(self) -> None:
        mode_text = tr("mode_mouse") if self.ui_settings.trigger_mode == "mouse" else tr("mode_keyboard")
        if self.ui_settings.trigger_mode == "mouse":
            mode_text += f" {self.ui_settings.mouse_button}"
        else:
            mode_text += f" {normalize_keyboard_hotkey(self.ui_settings.keyboard_hotkey)}"
        self.trigger_item.title = f'{tr("trigger_prefix")}: {mode_text}'
        self.status_item.title = f'{tr("status_prefix")}: {localized_status(self.current_status)}'
        self.auto_on_item.title = tr("menu_auto_on")
        self.launch_login_item.title = tr("menu_launch_login")
        self.toggle_item.title = tr("menu_toggle")
        self.hotkey_settings_item.title = tr("menu_hotkey_settings")
        self.model_config_item.title = tr("menu_model_config")
        self.update_model_item.title = tr("menu_update_model")
        self.quit_item.title = tr("menu_quit")
        self.build_item.title = f'{tr("build_prefix")}: {APP_BUILD}'

        self.auto_on_item.state = 1 if self.ui_settings.enable_dictation_on_app_start else 0
        self.launch_login_item.state = 1 if is_os_autostart_enabled() else 0

    def _migrate_autostart_if_needed(self) -> None:
        if not is_os_autostart_enabled():
            return
        if not is_os_autostart_legacy() and not is_os_autostart_runner_outdated():
            return
        try:
            set_os_autostart_enabled(True)
            logging.info("autostart migrated to runner: %s", AUTOSTART_RUNNER)
        except Exception as exc:
            logging.exception("autostart migration failed: %s", exc)
            self._queue_alert(tr("autostart_migrate_failed"))

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
            "OFF": "FA○",
            "LOADING": "FA…",
            "UPDATING": "FA⇡",
            "READY": "FA✓",
            "RECORDING": "FA●",
            "TRANSCRIBING": "FA↻",
            "ERROR": "FA!",
        }
        self.title = title_map.get(status, "FA•")
        if self.title != self.last_published_title:
            self.last_published_title = self.title
            logging.info("menubar title updated: %s (status=%s)", self.title, status)
        self._ensure_status_item_visible()
        self.status_item.title = f'{tr("status_prefix")}: {localized_status(status)}'

    @rumps.clicked("Toggle Dictation")
    def on_toggle_dictation(self, _):
        if self.dictation_enabled:
            self.disable_dictation()
        else:
            self.enable_dictation(show_alert=True, request_prompt=True)

    def _set_trigger_mode(self, mode: str) -> None:
        self.ui_settings.trigger_mode = mode
        save_ui_settings(self.ui_settings)
        self.refresh_ui_labels()
        self.restart_trigger()

    def _set_keyboard_hotkey_flow(self) -> None:
        try:
            logging.info("on_set_hotkey: start")
            was_enabled = self.dictation_enabled
            if was_enabled:
                self.trigger.stop()
            value = choose_hotkey_with_capture(self.ui_settings.keyboard_hotkey)

            if not value:
                ui_alert_native(tr("no_key_captured"), title=tr("menu_set_hotkey"))
                if was_enabled:
                    self.restart_trigger()
                return

            self.ui_settings.keyboard_hotkey = value
            self.ui_settings.trigger_mode = "keyboard"
            save_ui_settings(self.ui_settings)
            self.refresh_ui_labels()
            if was_enabled:
                self.restart_trigger()
            ui_alert_native(tr("hotkey_saved", value=value), title=tr("menu_set_hotkey"))
            logging.info("on_set_hotkey: saved=%s", value)
        except Exception as exc:
            logging.exception("on_set_hotkey crashed: %s", exc)
            ui_alert_native(tr("hotkey_set_failed", error=exc), title=tr("menu_set_hotkey"))

    def _set_mouse_button_flow(self) -> None:
        try:
            logging.info("on_set_mouse_button: start")
            was_enabled = self.dictation_enabled
            if was_enabled:
                self.trigger.stop()

            value = choose_mouse_button_with_capture(self.ui_settings.mouse_button)
            if not value:
                ui_alert_native(tr("no_mouse_captured"), title=tr("menu_set_mouse"))
                if was_enabled:
                    self.restart_trigger()
                return

            self.ui_settings.mouse_button = value
            self.ui_settings.trigger_mode = "mouse"
            save_ui_settings(self.ui_settings)
            self.refresh_ui_labels()
            if was_enabled:
                self.restart_trigger()
            ui_alert_native(tr("mouse_saved", value=value), title=tr("menu_set_mouse"))
            logging.info("on_set_mouse_button: saved=%s", value)
        except Exception as exc:
            logging.exception("on_set_mouse_button crashed: %s", exc)
            ui_alert_native(tr("mouse_set_failed", error=exc), title=tr("menu_set_mouse"))

    @rumps.clicked("Hotkey Settings")
    def on_hotkey_settings(self, _):
        while True:
            action = ui_hotkey_settings_action(self.ui_settings)
            if action == "done":
                return
            if action == "use_keyboard":
                self._set_trigger_mode("keyboard")
                continue
            if action == "use_mouse":
                self._set_trigger_mode("mouse")
                continue
            if action == "set_keyboard":
                self._set_keyboard_hotkey_flow()
                continue
            if action == "set_mouse":
                self._set_mouse_button_flow()
                continue

    @rumps.clicked("Model Config")
    def on_model_config(self, _):
        try:
            started = time.monotonic()
            logging.info("on_model_config: open")
            edited = ui_edit_model_config(self.core_config)
            if edited is None:
                logging.info("on_model_config: canceled after %.3fs", time.monotonic() - started)
                return
            save_core_config(edited)
            self.core_config = load_core_config()
            self.engine.config = self.core_config
            logging.info(
                "on_model_config: saved language=%s sample_rate=%s channels=%s use_itn=%s merge_vad=%s remove_emoji=%s hotwords_len=%s",
                self.core_config.language,
                self.core_config.sample_rate,
                self.core_config.channels,
                self.core_config.use_itn,
                self.core_config.merge_vad,
                self.core_config.remove_emoji,
                len((self.core_config.hotwords or "").strip()),
            )
            logging.info("on_model_config: saved in %.3fs", time.monotonic() - started)
            ui_alert_native(tr("model_config_saved"), title=tr("menu_model_config"))
        except Exception as exc:
            logging.exception("on_model_config failed: %s", exc)
            ui_alert_native(tr("model_config_save_failed", error=exc), title=tr("menu_model_config"))

    @rumps.clicked("Update Model")
    def on_update_model(self, _):
        if self.updating_model:
            ui_alert_native(tr("update_in_progress"), title=tr("menu_update_model"))
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

            self.engine = DictationEngine(
                self.core_config,
                self.on_engine_status,
                self._queue_alert,
            )
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
                self._queue_alert(tr("update_timeout_failed"))
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

            self._queue_alert(tr("update_completed"))
            logging.info("update_model: completed")
        except Exception as exc:
            logging.exception("update_model failed: %s", exc)
            self.on_engine_status("ERROR")
            self._queue_alert(tr("update_failed", error=exc))
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
            ui_alert_native(
                tr("launch_login_update_failed", error=exc),
                title=tr("menu_launch_login"),
            )

    @rumps.clicked("Quit App")
    def on_quit(self, _):
        self.trigger.stop()
        self.engine.stop_all()
        rumps.quit_application()


def main() -> None:
    if not acquire_single_instance():
        logging.info("another instance exists, skip launch")
        try:
            ui_alert(tr("already_running_hint"), title=tr("app_name"))
        except Exception:
            pass
        return
    atexit.register(release_single_instance)

    # Keep the app in menu bar mode (hide Dock icon where possible).
    try:
        bundle = NSBundle.mainBundle()
        if bundle is not None and bundle.infoDictionary() is not None:
            bundle.infoDictionary()["LSUIElement"] = "1"
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        # If launched hidden (e.g. by LaunchAgent/open flags), force unhide so
        # the menu bar icon/status is visible.
        try:
            app.unhideWithoutActivation()
        except Exception:
            try:
                app.unhide_(None)
            except Exception:
                pass
        # Force app icon for all NSAlert/NSWindow created by rumps (avoid Python rocket icon).
        if Path(APP_ICON).exists():
            icon = NSImage.alloc().initWithContentsOfFile_(APP_ICON)
            if icon is not None:
                app.setApplicationIconImage_(icon)
    except Exception:
        pass

    log_runtime_context()

    app = SenseVoiceMenuBarApp()
    logging.info("main: app initialized, entering run loop")
    app.run()


if __name__ == "__main__":
    main()
