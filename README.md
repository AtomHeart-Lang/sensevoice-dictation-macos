# FunASR Dictation for macOS

FunASR Dictation is a macOS menubar app for push-to-talk dictation, running on [Fun-ASR-Nano-2512](https://github.com/FunAudioLLM/Fun-ASR):
- press the trigger once to start recording
- press again to stop
- transcribe with Fun-ASR-Nano-2512
- auto-paste into the active text box

Compared with built-in dictation or many generic tools, this app focuses on:
- Local inference on your Mac (lower latency and no mandatory cloud round-trip)
- Newer open model foundation (Fun-ASR) with practical updates via `Update Model`
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
- Python 3.11+ (installer will auto-install via Homebrew when missing)
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
4. pre-download Fun-ASR-Nano-2512 + VAD models
5. create launcher app in `~/Applications` and Desktop shortcut symlink
6. if Python 3.11+ is missing, auto-install Python via Homebrew (when `brew` is available)

Installer options:
- `--no-model`
- `--no-launcher`
- `--autostart`

## Run

```bash
./start_app.sh
```

Or run from desktop/application icon after `./create_launcher.sh`.

## Fun-ASR Tuning

Use menu `Model Config` to edit and save runtime parameters directly in UI.

The UI writes values into `config.toml` for persistence. Manual file editing is optional.

- `language`: `auto|zh|en|ja` (for mixed Chinese/English dictation, keep `auto`)
- `Normalize Numbers/Dates` (`use_itn`): ON makes numeric/date text cleaner
- `Merge Long-Pause Segments` (`merge_vad`): ON may improve speed for long audio, OFF usually gives better sentence breaks
- `hotwords`: domain terms for names/brands/jargon (comma/newline separated in UI)
- `remove_emoji`: remove emoji symbols from final pasted text

Default recommended preset in this release:
- `language = "auto"`
- `sample_rate = 16000`
- `channels = 1`
- `paste_delay_ms = 20`
- `enable_beep = true`
- `use_itn = true`
- `merge_vad = false`
- `hotwords = ""`
- `remove_emoji = true`
- `batch_size_s = 0` (fixed internal runtime value; not user-facing in UI)

You can also edit these at runtime from menu `Model Config` (no manual file editing required).

Model Config fields in UI (localized by system language):
- Recognition Language (`language`)
- Sample Rate / Channels / Paste Delay
- Hot Words (large multiline input box; comma/newline separated)
- Record Beeps (`enable_beep`)
- Normalize Numbers/Dates (`use_itn`)
- Merge Long-Pause Segments (`merge_vad`)
- Remove Emoji Symbols (`remove_emoji`)

### Input/Paste recommendations

- `sample_rate`: recommended `16000`; use `44100`/`48000` only when your microphone driver requires it.
- `channels`: recommended `1` (mono); use `2` only for true stereo capture devices.
- `paste_delay_ms`: recommended `20-40`; if paste occasionally fails, increase to `60`.
- These recommendations are shown directly in the Model Config UI.

### Option behavior (plain-language)

`Normalize Numbers/Dates` (`use_itn`)
- ON: cleaner text formatting for numbers, dates, and units.
- OFF: closer to raw spoken form.

`Merge Long-Pause Segments` (`merge_vad`)
- ON: may reduce decoding overhead for long audio.
- OFF: usually better punctuation and sentence boundary stability.

`Hot Words` (`hotwords`)
- Add high-frequency domain words (names, products, technical terms).
- In UI, input one term per line or comma-separated; app normalizes and deduplicates automatically.
- Start from 5-50 terms and keep the list focused.

### How to change

1. Open menu `Model Config`.
2. Edit values and click `Save`.
3. Changes apply from the next recording.

Optional (advanced): edit `config.toml` manually, for example:

```toml
language = "zh"
merge_vad = false
use_itn = true
hotwords = "OpenAI, GitHub, LaunchAgent"
remove_emoji = true
# runtime compatibility value (fixed):
batch_size_s = 0
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
- `funasr_nano_runtime/`: bundled Fun-ASR runtime source files (`model.py`, `ctc.py`, `tools/utils.py`) required by `Fun-ASR-Nano-2512`

### Uninstall behavior

`./uninstall.sh` removes:
- launch agents
- running app processes
- Fun-ASR-Nano-2512 model cache (and legacy SenseVoice cache if present)
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
- If you still see old `SenseVoice Dictation` rows in Privacy settings, reset old entries once:
  - `tccutil reset Accessibility com.lee.sensevoice.dictation.launcher`
  - `tccutil reset ListenEvent com.lee.sensevoice.dictation.launcher`
  - `tccutil reset Accessibility com.lee.sensevoice.menubar`
  - `tccutil reset ListenEvent com.lee.sensevoice.menubar`
  - Then run `./create_launcher.sh`, reopen `FunASR Dictation.app`, and re-enable permissions for the new entry.

## GitHub Sharing

Create a release package:

```bash
./prepare_release.sh
```

Generated file:
- `sensevoice-dictation-macos-release.zip`

## Chinese Documentation

- `README.zh-CN.md`
