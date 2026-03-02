# SenseVoice Dictation for macOS (Bilingual / 中英双语)

A macOS menubar app for press-to-record, speech-to-text, and auto-paste into any text box.
这是一个 macOS 菜单栏语音转文字应用：按快捷键开始录音，再按一次停止，自动转写并粘贴到当前文本框。

## Quick Start / 快速开始

1. Install / 安装
```bash
./install.sh
```

2. Run / 启动
```bash
./start_app.sh
```

3. Optional autostart / 可选：开机自启
```bash
./enable_autostart.sh
```

4. Optional clickable launcher / 可选：创建可点击桌面与应用图标
```bash
./create_launcher.sh
```

## Main Scripts / 主要脚本

- `install.sh`: one-click install dependencies + optional model prefetch + launcher creation.
- `start_app.sh`: start menubar app.
- `enable_autostart.sh` / `disable_autostart.sh`: manage macOS LaunchAgent.
- `create_launcher.sh` / `remove_launcher.sh`: create/remove `.app` launcher in `~/Applications` and Desktop.
- `uninstall.sh`: full uninstall (venv, model cache, launcher, launch agents, runtime files).
- `prepare_release.sh`: clean local artifacts and create a GitHub-ready zip package.

Legacy compatibility wrappers are still kept:
`install_local_dependencies.sh`, `start_menubar_app.sh`, `enable_menubar_autostart.sh`, `disable_menubar_autostart.sh`, `create_clickable_launcher.sh`, `remove_clickable_launcher.sh`, `uninstall_sensevoice_hotkey.sh`.

## Permissions / 权限

Grant these permissions to your terminal / launcher process:
- Microphone
- Accessibility
- Input Monitoring

## Settings / 设置

- Keyboard hotkey / 键盘快捷键: menu -> `Set Keyboard Hotkey`
- Mouse trigger / 鼠标触发键: menu -> `Set Mouse Button`
- Trigger mode / 触发方式切换: `Use Keyboard Trigger` / `Use Mouse Trigger`
- Model update / 更新模型: menu -> `Update Model`

Key token reference: see `可用快捷键字符列表.txt`.

## Uninstall / 卸载

Standard uninstall (keep source folder):
```bash
./uninstall.sh
```

Full uninstall including source folder:
```bash
./uninstall.sh --delete-project-dir
```

## Detailed Docs / 详细文档

- Chinese: `README.zh-CN.md`
- English: `README.en.md`
- Script reference (CN+EN): `SCRIPTS.md`
