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
