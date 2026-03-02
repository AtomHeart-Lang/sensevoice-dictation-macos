# SenseVoice Dictation（macOS）中文说明

## 1. 项目简介

这是一个 macOS 菜单栏语音输入工具：
- 按一次快捷键开始录音
- 再按一次快捷键停止录音
- 自动调用 SenseVoice 转写并粘贴到当前输入框

支持键盘触发和鼠标按键触发，支持状态栏显示、开机自启、桌面快捷方式和模型更新。

## 2. 环境要求

- macOS 11+
- Python 3.11+
- Xcode Command Line Tools（用于构建 `.app` 启动器，`clang`）

可选依赖：
- `ffmpeg`（当前方案可不装）

## 3. 安装部署

```bash
./install.sh
```

默认会执行：
1. 创建并配置 `.venv`
2. 安装 `requirements.txt` 依赖
3. 生成 `config.toml`（若不存在）
4. 预下载 SenseVoice + VAD 模型
5. 创建可点击启动器（应用程序 + 桌面）

可选参数：
- `--no-model`：跳过模型预下载
- `--no-launcher`：不创建 `.app` 启动器
- `--autostart`：安装后直接开启开机自启

## 4. 启动与使用

启动：
```bash
./start_app.sh
```

状态栏状态：
- `○` 关闭
- `…` 加载中
- `⇡` 更新模型中
- `✓` 就绪
- `●` 录音中
- `↻` 转写中
- `!` 错误

菜单功能：
- `Toggle Dictation`
- `Use Keyboard Trigger`
- `Use Mouse Trigger`
- `Set Keyboard Hotkey`
- `Set Mouse Button`
- `Update Model`
- `Enable Dictation On App Start`
- `Quit App`

快捷键可用字符见：`可用快捷键字符列表.txt`

## 5. 开机自启

启用：
```bash
./enable_autostart.sh
```

关闭：
```bash
./disable_autostart.sh
```

## 6. 创建/删除快捷方式图标

创建：
```bash
./create_launcher.sh
```

删除：
```bash
./remove_launcher.sh
```

## 7. 升级模型

方式一：菜单中点击 `Update Model`。

方式二：卸载模型缓存后重新运行安装脚本：
```bash
./uninstall.sh
./install.sh
```

## 8. 卸载与清理

标准卸载（保留项目源码目录）：
```bash
./uninstall.sh
```

会清理：
- LaunchAgent
- 运行中进程
- 模型缓存
- `.venv`
- 日志/锁文件/本地配置
- 应用程序与桌面启动器

彻底卸载（连项目目录一起删除）：
```bash
./uninstall.sh --delete-project-dir
```

## 9. 发布到 GitHub 建议

生成干净发布包（可选）：
```bash
./prepare_release.sh
```

1. 确保 `.gitignore` 已生效（不提交 `.venv`、日志、本地配置）
2. 提交核心文件：
   - `menubar_dictation_app.py`
   - `assets/mic_menu_icon.png`
   - `requirements.txt`
   - `config.example.toml`
   - 脚本与文档
3. 在 README 中给出 3 条最短路径：
   - `./install.sh`
   - `./start_app.sh`
   - `./uninstall.sh`
