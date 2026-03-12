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
- Graphical uninstaller app in `~/Applications`
- Optional Desktop shortcut as a symlink to the same app (prevents duplicate permission entries)
- DMG packaging flow for non-technical users (installer downloads standalone Python, dependencies, and latest model during setup)
- Native installer/uninstaller progress windows on macOS (no Terminal window required)
- One-command uninstall and cleanup

## Requirements

- macOS 11+
- Python 3.11+ only for source installs (`./install.sh`)
- Xcode Command Line Tools (`clang`) only for source installs when no bundled launcher binary is present

Optional:
- `ffmpeg` (not required by this app flow)

## DMG Installation

The DMG installer is designed for normal users:
- the DMG does not include the model cache
- no Homebrew or preinstalled Python is required
- installation downloads a standalone Python runtime, Python dependencies, and the latest model during setup
- runtime files are copied to `~/Library/Application Support/FunASRDictation/app`
- bundled Python runtime is stored under `~/Library/Application Support/FunASRDictation/python-runtime`
- the final clickable app is created at `~/Applications/FunASR Dictation.app`
- a graphical uninstaller app is also created at `~/Applications/Uninstall FunASR Dictation.app`

To build the installer DMG locally:

```bash
./build_dmg.sh
```

Output:

```bash
./funasr-dictation-installer-2.1.7.dmg
```

Inside the DMG, double-click `Install FunASR Dictation.app`. A native macOS installer window appears, shows live progress/log output, downloads a standalone Python runtime, installs dependencies, downloads the latest model, then rebuilds the final launcher app with the stable TCC identity used by this project.

When installation finishes:
- the installer no longer auto-launches the app
- you can optionally click `Create Desktop Shortcut`
- the installer warns that macOS may require manual deletion of the Desktop shortcut during uninstall
- then click `Open App`, or launch `~/Applications/FunASR Dictation.app` manually

This avoids a macOS Privacy & Security extension crash that can happen if permission prompts are triggered while the installer window is still frontmost.

## Installation

```bash
./install.sh
```

Default installer behavior:
1. create `.venv`
2. install Python dependencies (`requirements.txt`)
3. create `config.toml` from `config.example.toml` if missing
4. pre-download Fun-ASR-Nano-2512 + VAD models
5. create launcher app in `~/Applications`
6. Desktop shortcut is optional and can be created later with `./create_desktop_shortcut.sh`
6. if Python 3.11+ is missing, auto-install Python via Homebrew (when `brew` is available)

Installer options:
- `--no-model`
- `--no-launcher`
- `--autostart`

## Run

```bash
./start_app.sh
```

Or run from the application icon after `./create_launcher.sh`. If you want a Desktop shortcut too, run `./create_desktop_shortcut.sh`.

For DMG installs, launch by double-clicking `Install FunASR Dictation.app` inside the DMG instead of running `install.sh` manually.

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
- `idle_unload_seconds = 300`
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
- Idle Model Unload Seconds (`idle_unload_seconds`)
- Hot Words (large multiline input box; comma/newline separated)
- Record Beeps (`enable_beep`)
- Normalize Numbers/Dates (`use_itn`)
- Merge Long-Pause Segments (`merge_vad`)
- Remove Emoji Symbols (`remove_emoji`)

### Input/Paste recommendations

- `sample_rate`: recommended `16000`; use `44100`/`48000` only when your microphone driver requires it.
- `channels`: recommended `1` (mono); use `2` only for true stereo capture devices.
- `paste_delay_ms`: recommended `20-40`; if paste occasionally fails, increase to `60`.
- `idle_unload_seconds`: recommended `300`; set `0` to keep the model loaded forever. Lower values reduce idle memory sooner, but the next use after idle will reload the model.
- These recommendations are shown directly in the Model Config UI.

### Option behavior (plain-language)

`Normalize Numbers/Dates` (`use_itn`)
- ON: cleaner text formatting for numbers, dates, and units.
- OFF: closer to raw spoken form.

`Merge Long-Pause Segments` (`merge_vad`)
- ON: may reduce decoding overhead for long audio.
- OFF: usually better punctuation and sentence boundary stability.

`Idle Model Unload Seconds` (`idle_unload_seconds`)
- `0`: never unload the ASR model while dictation stays enabled.
- `300` (recommended): unload model memory after 5 idle minutes and reload on next use.
- Lower values: save memory more aggressively, but the first use after idle will wait for model reload.

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
- `Hotkey Settings`
- `Model Config`
- `Update Model`
- `Enable Dictation On App Start`
- `Enable Launch At Login`
- `Quit App`

### Menu Name Mapping (EN/CN)

- `Toggle Dictation` / `开关语音输入`
- `Hotkey Settings` / `快捷键设置`
- `Model Config` / `模型参数设置`
- `Update Model` / `更新模型`
- `Enable Dictation On App Start` / `应用启动时自动开启听写`
- `Enable Launch At Login` / `开机自动启动`
- `Quit App` / `退出应用`

## Trigger Setup Flow

1. Click `Hotkey Settings`.
2. The dialog shows current trigger mode, current keyboard hotkey, and current mouse button.
3. Click `Set Keyboard Hotkey` or `Set Mouse Button`:
   - Choose `Start Capture` to auto-detect.
   - Or choose `Manual Input` to enter token text directly.
4. After setting keys, click `Use Keyboard Trigger` or `Use Mouse Trigger` to switch active trigger mode.
5. Click `Done` to close.

Hotkey/mouse trigger settings are persisted at:
- `~/Library/Application Support/SenseVoiceDictation/ui_settings.json`

This file survives app restarts and macOS reboots.

## Script Reference

### Core scripts

- `install.sh`: install environment/dependencies and optional setup steps
- `start_app.sh`: start menubar app
- `enable_autostart.sh`: enable LaunchAgent autostart
- `disable_autostart.sh`: disable LaunchAgent autostart
- `create_launcher.sh`: create clickable `.app` launcher in Applications
- `create_desktop_shortcut.sh`: create the optional Desktop shortcut symlink
- `create_uninstaller.sh`: create graphical uninstaller app in Applications
- `launch_from_desktop.sh`: desktop launcher entrypoint (silent background startup)
- `remove_launcher.sh`: remove launcher app + Desktop shortcut symlink
- `uninstall.sh`: uninstall and cleanup runtime/model/env
- `prepare_release.sh`: clean artifacts and produce release zip
- `build_dmg.sh`: build the DMG installer for end users
- `install_from_dmg.command`: installer entrypoint used inside the DMG app bundle
- `download_python_runtime.sh`: download and verify the pinned standalone Python runtime for DMG installs
- `task_runner/TaskProgressApp.m`: native macOS task window used by the installer/uninstaller
- `launcher/FunASRLauncher.c`: launcher source that requests TCC and resolves runtime path from Application Support
- `funasr_nano_runtime/`: bundled Fun-ASR runtime source files (`model.py`, `ctc.py`, `tools/utils.py`) required by `Fun-ASR-Nano-2512`

### Uninstall behavior

`./uninstall.sh` removes:
- launch agents
- running app processes
- Fun-ASR-Nano-2512 model cache (and legacy SenseVoice cache if present)
- `.venv`
- local logs/locks/runtime config
- `~/Library/Application Support/SenseVoiceDictation/ui_settings.json` and related config residues
- launcher / uninstaller apps in Applications/Desktop
- DMG-installed runtime directory under `~/Library/Application Support/FunASRDictation`
- TCC entries for known app identifiers (best effort reset)

Desktop shortcut removal is best-effort:
- if macOS blocks automatic removal from Desktop, uninstall still completes
- the uninstaller shows a warning telling you to delete the Desktop shortcut manually

Also supports full source or DMG runtime removal:

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
- Recommended workflow: open `Hotkey Settings` -> `Set Mouse Button`, then click your target mouse key to auto-capture and save.
- Manual input is still supported for `middle`, `x1`, `x2`, and `buttonN` (`N >= 2`, except `0/1`).
- For Logitech MX series: if side buttons are configured as gestures/keystrokes in Logi Options+, they may not appear as mouse button events. Set them to `Generic Button` first, or use keyboard trigger mode.

## Permissions

Grant permissions to the actual running process chain:
- Microphone
- Accessibility
- Input Monitoring

Notes:
- For first-time permission enrollment, launch by double-clicking `~/Applications/FunASR Dictation.app` (or the optional Desktop shortcut if you created one), not `./start_app.sh`.
- Launcher now requests Microphone/Accessibility/Input-Monitoring at app startup (you should see system permission prompts on first run).
- If launch from Terminal works but launcher fails, re-create launcher and re-check permissions.
- If created, the Desktop shortcut points to the same app in `~/Applications` to avoid duplicate TCC rows.
- If `open -a "FunASR Dictation"` cannot find the app on first install, run:
  - `open "$HOME/Applications/FunASR Dictation.app"`
- Recording uses the macOS system default input device (no in-app auto device switching).
- If hotkey works but recognition is always empty, check Microphone permission and Sound Input device (the app warns when captured audio is all-zero).
- Permission identity migration (one-time, if permissions keep resetting):
  - `./create_launcher.sh --force-rebuild`
  - Reopen `FunASR Dictation.app` and grant permissions once.
  - The launcher now keeps one stable bundle ID (`com.lee.sensevoice.dictation.launcher`) and auto-cleans legacy `com.lee.funasr.dictation.launcher` TCC leftovers.

## GitHub Sharing

Create a release package:

```bash
./prepare_release.sh
```

Generated file:
- `sensevoice-dictation-macos-release.zip`

## Chinese Documentation

- `README.zh-CN.md`
