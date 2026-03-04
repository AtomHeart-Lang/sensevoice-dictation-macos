# SenseVoice Dictation for macOS

SenseVoice Dictation is a macOS menubar app for push-to-talk dictation, built on [SenseVoice](https://github.com/FunAudioLLM/SenseVoice):
- press the trigger once to start recording
- press again to stop
- transcribe with SenseVoice
- auto-paste into the active text box

Compared with built-in dictation or many generic tools, this app focuses on:
- Local inference on your Mac (lower latency and no mandatory cloud round-trip)
- Newer open model foundation (SenseVoice) with practical updates via `Update Model`
- Strong mixed Chinese/English recognition quality in real typing workflows
- End-to-end automation for global hotkey trigger and auto-paste into any text field

## Features

- Menubar status indicators (off/loading/updating/ready/recording/transcribing/error)
- UI language follows system language: Chinese system -> all menus/prompts in Chinese; all other languages -> English
- Keyboard trigger and mouse trigger
- Manual trigger configuration dialogs
- Model refresh from menu (`Update Model`)
- OS autostart toggle from menu (`Enable Launch At Login`)
- Dictation-on-app-start toggle from menu (`Enable Dictation On App Start`)
- Clickable launcher app in `~/Applications`
- Desktop shortcut as a symlink to the same app (prevents duplicate permission entries)
- One-command uninstall and cleanup

## Requirements

- macOS 11+
- Python 3.11+
- Xcode Command Line Tools (`clang`) for launcher generation

Optional:
- `ffmpeg` (not required by this app flow)

## Installation

```bash
./install.sh
```

Default installer behavior:
1. create `.venv`
2. install Python dependencies (`requirements.txt`)
3. create `config.toml` from `config.example.toml` if missing
4. pre-download SenseVoice + VAD models
5. create launcher app in `~/Applications` and Desktop shortcut symlink

Installer options:
- `--no-model`
- `--no-launcher`
- `--autostart`

## Run

```bash
./start_app.sh
```

Or run from desktop/application icon after `./create_launcher.sh`.

## SenseVoice Tuning

Use menu `Model Config` to edit and save runtime parameters directly in UI.

The UI writes values into `config.toml` for persistence. Manual file editing is optional.

- `language`: `auto|zh|en|yue|ja|ko|nospeech` (for Chinese accuracy, prefer `zh`)
- `use_itn`: enable text normalization for numbers/date formatting
- `batch_size_s`: inference batch seconds (default `9`)
- `merge_vad`: merge VAD segments (default `false`)
- `remove_emoji`: remove emoji symbols from final pasted text (default `true`)

Default recommended preset in this release:
- `language = "auto"`
- `sample_rate = 16000`
- `channels = 1`
- `paste_delay_ms = 20`
- `enable_beep = true`
- `use_itn = true`
- `batch_size_s = 9`
- `merge_vad = false`
- `remove_emoji = true`

You can also edit these at runtime from menu `Model Config` (no manual file editing required).

Model Config fields in UI:
- `language`
- `sample_rate`
- `channels`
- `paste_delay_ms`
- `batch_size_s`
- `enable_beep`
- `use_itn`
- `merge_vad`
- `remove_emoji`

### `batch_size_s` (speed vs. precision)

- Meaning: how many seconds of speech are packed per decoding batch.
- Larger value: fewer decode rounds, usually faster overall.
- Smaller value: finer-grained decoding, usually a bit more stable for punctuation/word boundaries.
- Recommended range: `6` to `12`.

Practical presets:
- Accuracy-first dictation: `batch_size_s = 6`
- Balanced default: `batch_size_s = 9`
- Long-form speed-first: `batch_size_s = 12`

### `merge_vad` (segment strategy)

- Meaning: whether to merge neighboring VAD (voice activity detection) segments before decoding.
- `false` (default in this project): keep segments separated for stronger segmentation stability.
- `true`: merge segments and reduce decode overhead in some scenarios.

Practical recommendation:
- For the current project preset (fast + stable in real usage): keep `merge_vad = false`.

### How to change

1. Open menu `Model Config`.
2. Edit values and click `Save`.
3. Changes apply from the next recording.

Optional (advanced): edit `config.toml` manually, for example:

```toml
language = "zh"
batch_size_s = 9
merge_vad = false
use_itn = true
remove_emoji = true
```

Then restart the menubar app.

## Menubar States

- `○` OFF
- `…` LOADING
- `⇡` UPDATING
- `✓` READY
- `●` RECORDING
- `↻` TRANSCRIBING
- `!` ERROR

## Menu Items

- `Toggle Dictation`
- `Use Keyboard Trigger`
- `Use Mouse Trigger`
- `Set Keyboard Hotkey`
- `Set Mouse Button`
- `Model Config`
- `Update Model`
- `Enable Dictation On App Start`
- `Enable Launch At Login`
- `Quit App`

### Menu Name Mapping (EN/CN)

- `Toggle Dictation` / `开关语音输入`
- `Use Keyboard Trigger` / `使用键盘触发`
- `Use Mouse Trigger` / `使用鼠标触发`
- `Set Keyboard Hotkey` / `设置键盘快捷键`
- `Set Mouse Button` / `设置鼠标按键`
- `Model Config` / `模型参数设置`
- `Update Model` / `更新模型`
- `Enable Dictation On App Start` / `应用启动时自动开启听写`
- `Enable Launch At Login` / `开机自动启动`
- `Quit App` / `退出应用`

## Trigger Setup Flow

### Set Keyboard Hotkey

1. Click `Set Keyboard Hotkey`.
2. Choose `Start Capture` or `Manual Input`.
3. If capture is chosen, the app listens for 8 seconds and shows a notification prompt.
4. If key capture succeeds, the recognized hotkey is pre-filled for confirmation/editing.
5. If capture fails, you can retry capture or switch to manual input.

Hotkey/mouse trigger settings are persisted at:
- `~/Library/Application Support/SenseVoiceDictation/ui_settings.json`

This file survives app restarts and macOS reboots.

### Set Mouse Button

1. Click `Set Mouse Button`.
2. Choose `Start Capture` or `Manual Input`.
3. If capture is chosen, the app listens for mouse button events (left/right ignored).
4. If capture succeeds, the recognized button token is pre-filled for confirmation/editing.
5. If capture fails, you can retry capture or switch to manual input.

## Script Reference

### Core scripts

- `install.sh`: install environment/dependencies and optional setup steps
- `start_app.sh`: start menubar app
- `enable_autostart.sh`: enable LaunchAgent autostart
- `disable_autostart.sh`: disable LaunchAgent autostart
- `create_launcher.sh`: create clickable `.app` launcher in Applications + Desktop symlink
- `launch_from_desktop.sh`: desktop launcher entrypoint (silent background startup)
- `remove_launcher.sh`: remove launcher app + Desktop shortcut symlink
- `uninstall.sh`: uninstall and cleanup runtime/model/env
- `prepare_release.sh`: clean artifacts and produce release zip

### Uninstall behavior

`./uninstall.sh` removes:
- launch agents
- running app processes
- SenseVoice model cache
- `.venv`
- local logs/locks/runtime config
- `~/Library/Application Support/SenseVoiceDictation/ui_settings.json` and related config residues
- launcher apps in Applications/Desktop
- TCC entries for known app identifiers (best effort reset)

Also supports full source removal:

```bash
./uninstall.sh --delete-project-dir
```

## Keyboard Hotkey Token List

### Format

- Use `modifier+key`, for example:
  - `<ctrl>+a`
  - `<ctrl>+<left>`
  - `<cmd>+<shift>+<f8>`

### Modifiers

- `<ctrl>`
- `<alt>`
- `<cmd>`
- `<shift>`

Notes:
- `<option>` is normalized to `<alt>`

### Main keys

Letters:
- `a` `b` `c` `d` `e` `f` `g` `h` `i` `j` `k` `l` `m` `n` `o` `p` `q` `r` `s` `t` `u` `v` `w` `x` `y` `z`

Numbers:
- `0 1 2 3 4 5 6 7 8 9`

Symbols:
- `=` `-` `[` `]` `;` `'` `\\` `,` `.` `/` `` ` ``

Special keys:
- `<space>`
- `<enter>`
- `<tab>`
- `<backspace>`
- `<delete>`
- `<esc>`
- `<left>` `<right>` `<up>` `<down>`
- `<home>` `<end>` `<pgup>` `<pgdn>`

Function keys:
- `<f1>` ... `<f19>`

## Mouse Trigger Token List

Supported values:
- `button2` -> `middle`
- `button3` -> `x1`
- `button4` -> `x2`
- `buttonN` (`N >= 5`, device-dependent)

Important:
- `left` and `right` are intentionally disabled to avoid conflicts with normal clicking.
- Mouse button numbering is device-dependent. `buttonN` means the raw button number reported by macOS for your specific mouse.
- Recommended workflow: use `Set Mouse Button` and click your target mouse key to auto-capture it, then save.
- Manual input is still supported for `middle`, `x1`, `x2`, and `buttonN` (`N >= 2`, except `0/1`).
- For Logitech MX series: if side buttons are configured as gestures/keystrokes in Logi Options+, they may not appear as mouse button events. Set them to `Generic Button` first, or use keyboard trigger mode.

## Permissions

Grant permissions to the actual running process chain:
- Microphone
- Accessibility
- Input Monitoring

Notes:
- If launch from Terminal works but launcher fails, re-create launcher and re-check permissions.
- Desktop shortcut points to the same app in `~/Applications` to avoid duplicate TCC rows.

## GitHub Sharing

Create a release package:

```bash
./prepare_release.sh
```

Generated file:
- `sensevoice-dictation-macos-release.zip`

## Chinese Documentation

- `README.zh-CN.md`
