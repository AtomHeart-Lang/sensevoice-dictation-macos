# SenseVoice Dictation (macOS) - English Guide

## 1. Overview

This is a macOS menubar dictation tool:
- Press hotkey once to start recording
- Press again to stop recording
- Auto-transcribe with SenseVoice and auto-paste into the active text field

It supports keyboard/mouse triggers, status in menubar, autostart, clickable launcher app, and model update.

## 2. Requirements

- macOS 11+
- Python 3.11+
- Xcode Command Line Tools (`clang`, required for launcher app generation)

Optional:
- `ffmpeg` (not required by current workflow)

## 3. Installation

```bash
./install.sh
```

By default it will:
1. Create `.venv`
2. Install Python dependencies
3. Create `config.toml` if missing
4. Pre-download SenseVoice + VAD models
5. Create launcher app in `~/Applications` and Desktop

Optional flags:
- `--no-model`
- `--no-launcher`
- `--autostart`

## 4. Run

```bash
./start_app.sh
```

Menubar states:
- `○` off
- `…` loading
- `⇡` updating model
- `✓` ready
- `●` recording
- `↻` transcribing
- `!` error

Menu items:
- `Toggle Dictation`
- `Use Keyboard Trigger`
- `Use Mouse Trigger`
- `Set Keyboard Hotkey`
- `Set Mouse Button`
- `Update Model`
- `Enable Dictation On App Start`
- `Quit App`

Hotkey tokens: `可用快捷键字符列表.txt`

## 5. Autostart

Enable:
```bash
./enable_autostart.sh
```

Disable:
```bash
./disable_autostart.sh
```

## 6. Launcher App

Create:
```bash
./create_launcher.sh
```

Remove:
```bash
./remove_launcher.sh
```

## 7. Model Update

Preferred: click `Update Model` in menu.

Alternative:
```bash
./uninstall.sh
./install.sh
```

## 8. Uninstall

Standard uninstall (keep source folder):
```bash
./uninstall.sh
```

This removes:
- launch agents
- running processes
- model cache
- `.venv`
- logs/locks/local config
- launcher apps

Full uninstall including source folder:
```bash
./uninstall.sh --delete-project-dir
```

## 9. Prepare GitHub Release Package

```bash
./prepare_release.sh
```
