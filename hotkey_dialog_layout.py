from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class HotkeyDialogItem:
    key: str
    label_key: str


@dataclass(frozen=True)
class HotkeyDialogSection:
    key: str
    title_key: str
    items: Tuple[HotkeyDialogItem, ...]


@dataclass(frozen=True)
class HotkeyDialogAction:
    key: str
    label_key: str
    emphasis: str = "secondary"


def build_hotkey_settings_sections() -> Tuple[HotkeyDialogSection, ...]:
    return (
        HotkeyDialogSection(
            key="mode",
            title_key="hotkey_dialog_section_mode",
            items=(
                HotkeyDialogItem("mode_keyboard", "mode_keyboard"),
                HotkeyDialogItem("mode_mouse", "mode_mouse"),
            ),
        ),
        HotkeyDialogSection(
            key="current",
            title_key="hotkey_dialog_section_current",
            items=(
                HotkeyDialogItem("keyboard_hotkey", "hotkey_settings_keyboard_line"),
                HotkeyDialogItem("mouse_button", "hotkey_settings_mouse_line"),
            ),
        ),
    )


def build_hotkey_settings_actions() -> Tuple[HotkeyDialogAction, ...]:
    return (
        HotkeyDialogAction(
            key="set_keyboard",
            label_key="menu_set_hotkey",
        ),
        HotkeyDialogAction(
            key="set_mouse",
            label_key="menu_set_mouse",
        ),
        HotkeyDialogAction(
            key="save",
            label_key="save",
            emphasis="primary",
        ),
    )
