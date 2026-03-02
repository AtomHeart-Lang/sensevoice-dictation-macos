# Script Reference / 脚本说明

## Recommended entrypoints / 推荐入口

- `install.sh`
- `start_app.sh`
- `enable_autostart.sh` / `disable_autostart.sh`
- `create_launcher.sh` / `remove_launcher.sh`
- `uninstall.sh`
- `prepare_release.sh`

## Script list / 脚本清单

1. `install.sh`
- EN: Installs Python env/deps, optionally pre-downloads model, optionally creates launcher/autostart.
- 中文：安装 Python 环境与依赖，可选预下载模型，可选创建启动器和开机自启。

2. `start_app.sh`
- EN: Starts the menubar app with single-instance guard.
- 中文：启动菜单栏应用，带单实例保护。

3. `enable_autostart.sh`
- EN: Creates and loads LaunchAgent `com.lee.sensevoice.menubar`.
- 中文：创建并加载开机自启 LaunchAgent。

4. `disable_autostart.sh`
- EN: Unloads and removes LaunchAgent.
- 中文：卸载并删除开机自启 LaunchAgent。

5. `create_launcher.sh`
- EN: Builds clickable `.app` launcher in `~/Applications` and Desktop.
- 中文：生成可点击 `.app` 启动器到“应用程序”和桌面。

6. `remove_launcher.sh`
- EN: Removes clickable launcher apps.
- 中文：删除可点击启动器。

7. `uninstall.sh`
- EN: Cleans launch agents, process, model cache, venv, logs, local config, launcher apps.
- 中文：清理自启、进程、模型缓存、虚拟环境、日志、本地配置、启动器。

8. `prepare_release.sh`
- EN: Cleans local artifacts and builds a zip package for GitHub release sharing.
- 中文：清理本地运行痕迹并打包生成可发布到 GitHub 的压缩包。

## Compatibility wrappers / 兼容包装脚本

These are kept to avoid breaking old commands:
这些脚本用于兼容旧命令，不建议新用户继续使用。

- `install_local_dependencies.sh` -> `install.sh`
- `start_menubar_app.sh` -> `start_app.sh`
- `enable_menubar_autostart.sh` -> `enable_autostart.sh`
- `disable_menubar_autostart.sh` -> `disable_autostart.sh`
- `create_clickable_launcher.sh` -> `create_launcher.sh`
- `remove_clickable_launcher.sh` -> `remove_launcher.sh`
- `uninstall_sensevoice_hotkey.sh` -> `uninstall.sh`
