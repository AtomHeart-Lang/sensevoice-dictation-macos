from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ModelConfigItem:
    key: str
    kind: str
    label_key: str
    help_key: Optional[str] = None


@dataclass(frozen=True)
class ModelConfigSection:
    key: str
    title_key: str
    items: Tuple[ModelConfigItem, ...]


@dataclass(frozen=True)
class ModelConfigDialogLayout:
    panel_w: int
    panel_h: int
    card_x: int
    card_w: int
    icon_x: int
    icon_y: int
    icon_size: int
    title_x: int
    title_y: int
    title_w: int
    title_h: int
    core_label_w: int
    core_field_x: int
    core_help_x: int
    toggle_help_x: int


def build_model_config_sections() -> Tuple[ModelConfigSection, ...]:
    return (
        ModelConfigSection(
            key="core",
            title_key="model_config_section_core",
            items=(
                ModelConfigItem("language", "text", "model_config_field_language"),
                ModelConfigItem(
                    "sample_rate",
                    "text",
                    "model_config_field_sample_rate",
                    "model_config_field_sample_rate_help",
                ),
                ModelConfigItem(
                    "channels",
                    "text",
                    "model_config_field_channels",
                    "model_config_field_channels_help",
                ),
                ModelConfigItem(
                    "paste_delay_ms",
                    "text",
                    "model_config_field_paste_delay",
                    "model_config_field_paste_delay_help",
                ),
                ModelConfigItem(
                    "idle_unload_seconds",
                    "text",
                    "model_config_field_idle_unload",
                    "model_config_field_idle_unload_help",
                ),
            ),
        ),
        ModelConfigSection(
            key="text",
            title_key="model_config_section_text",
            items=(
                ModelConfigItem("enable_beep", "toggle", "model_config_opt_beep"),
                ModelConfigItem(
                    "use_itn", "toggle", "model_config_opt_itn", "model_config_opt_itn_desc"
                ),
                ModelConfigItem(
                    "merge_vad",
                    "toggle",
                    "model_config_opt_merge_vad",
                    "model_config_opt_merge_vad_desc",
                ),
                ModelConfigItem(
                    "remove_emoji", "toggle", "model_config_opt_remove_emoji"
                ),
            ),
        ),
        ModelConfigSection(
            key="hotwords",
            title_key="model_config_section_hotwords",
            items=(
                ModelConfigItem(
                    "hotwords",
                    "multiline",
                    "model_config_field_hotwords",
                    "model_config_field_hotwords_help",
                ),
            ),
        ),
    )


def build_model_config_dialog_layout() -> ModelConfigDialogLayout:
    panel_w = 500
    panel_h = 790

    # NSAlert accessory views render with a slightly wider trailing gutter than
    # the leading side. Compensate inside the panel so the visible cards read
    # as centered in the full dialog window, not just inside the accessory view.
    card_left_inset = 40
    card_right_inset = 20
    card_w = panel_w - card_left_inset - card_right_inset

    icon_size = 52
    icon_x = 28
    icon_y = panel_h - 76

    title_h = 24
    title_x = 100
    title_y = icon_y + (icon_size - title_h) // 2
    title_w = panel_w - title_x - 20

    return ModelConfigDialogLayout(
        panel_w=panel_w,
        panel_h=panel_h,
        card_x=card_left_inset,
        card_w=card_w,
        icon_x=icon_x,
        icon_y=icon_y,
        icon_size=icon_size,
        title_x=title_x,
        title_y=title_y,
        title_w=title_w,
        title_h=title_h,
        core_label_w=128,
        core_field_x=160,
        core_help_x=44,
        toggle_help_x=44,
    )
