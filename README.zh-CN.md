# SenseVoice Dictation for macOS（中文说明）

SenseVoice Dictation 是一个 macOS 菜单栏语音输入工具：
- 按一次触发键开始录音
- 再按一次停止录音
- 使用 SenseVoice 转写
- 自动粘贴到当前输入框

## 功能特性

- 菜单栏状态指示（关闭/加载/更新/就绪/录音/转写/错误）
- UI 文案跟随系统语言：系统为中文时菜单/提示全中文；系统为英文或其他语言时全英文
- 支持键盘触发和鼠标触发
- 支持手动输入触发配置
- 支持在菜单中更新模型（`Update Model`）
- 支持在菜单中开关系统开机自启（`Enable Launch At Login`）
- 支持在菜单中开关“应用启动时自动开启听写”（`Enable Dictation On App Start`）
- 在 `~/Applications` 生成可点击启动器
- 桌面快捷方式是同一应用的符号链接（避免重复权限条目）
- 一键卸载并清理环境

## 环境要求

- macOS 11+
- Python 3.11+
- Xcode Command Line Tools（用于构建启动器，需要 `clang`）

可选：
- `ffmpeg`（当前流程不是必需）

## 安装

```bash
./install.sh
```

默认安装行为：
1. 创建 `.venv`
2. 安装 Python 依赖（`requirements.txt`）
3. 若不存在则从 `config.example.toml` 生成 `config.toml`
4. 预下载 SenseVoice + VAD 模型
5. 创建 `~/Applications` 启动器和桌面符号链接

安装参数：
- `--no-model`
- `--no-launcher`
- `--autostart`

## 启动

```bash
./start_app.sh
```

也可以在执行 `./create_launcher.sh` 后，直接双击应用/桌面图标启动。

## SenseVoice 调参

推荐直接在菜单 `Model Config` 中修改并保存参数（UI 方式）。

UI 保存后会自动写入 `config.toml` 持久化；手动改文件属于可选高级方式。

- `language`: `auto|zh|en|yue|ja|ko|nospeech`（中文场景建议用 `zh`）
- `use_itn`: 文本归一化（数字/日期格式化）
- `batch_size_s`: 推理 batch 秒数（默认 `11`）
- `merge_vad`: 是否合并 VAD 分段（默认 `true`）
- `remove_emoji`: 去除最终粘贴文本中的表情符号（默认 `true`）

本版本默认推荐参数：
- `language = "auto"`
- `sample_rate = 16000`
- `channels = 1`
- `paste_delay_ms = 20`
- `enable_beep = true`
- `use_itn = true`
- `batch_size_s = 11`
- `merge_vad = true`
- `remove_emoji = true`

也可以在菜单 `Model Config` 中直接修改这些运行参数（无需手动编辑文件）。

Model Config 窗口包含以下字段：
- `language`
- `sample_rate`
- `channels`
- `paste_delay_ms`
- `batch_size_s`
- `enable_beep`
- `use_itn`
- `merge_vad`
- `remove_emoji`

### `batch_size_s`（速度与精度权衡）

- 含义：每次解码打包的语音秒数。
- 值更大：解码轮次更少，通常整体更快。
- 值更小：解码粒度更细，通常对断句/标点边界更稳定一些。
- 建议范围：`6` 到 `12`。

实用预设：
- 精度优先听写：`batch_size_s = 6`
- 平衡默认：`batch_size_s = 11`
- 长语音速度优先：`batch_size_s = 12`

### `merge_vad`（分段策略）

- 含义：是否在解码前合并相邻 VAD（语音活动检测）分段。
- `false`：保持分段。
- `true`（本项目默认）：合并分段，实际听写中通常可减少解码开销、提升整体速度。

实用建议：
- 按当前项目默认（速度快且实测稳定）：建议保持 `merge_vad = true`。

### 如何修改

1. 打开菜单 `Model Config`
2. 修改参数后点击 `Save`
3. 新参数会从下一次录音开始生效

可选（高级）：手动编辑 `config.toml`，例如：

```toml
language = "zh"
batch_size_s = 11
merge_vad = true
use_itn = true
remove_emoji = true
```

然后重启菜单栏应用。

## 菜单栏状态

- `○` 关闭
- `…` 加载中
- `⇡` 更新中
- `✓` 就绪
- `●` 录音中
- `↻` 转写中
- `!` 错误

## 菜单项

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

### 菜单中英文名称对照

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

## 触发键设置流程

### Set Keyboard Hotkey（键盘触发）

1. 点击 `Set Keyboard Hotkey`。
2. 选择 `开始识别` 或 `手动输入`。
3. 若选择识别，程序会监听 8 秒，并弹出通知提醒你按下目标组合键。
4. 识别成功后，会自动回填到输入框，可直接保存或手动修改。
5. 识别失败时，可选择重试识别，或切换为手动输入。

### Set Mouse Button（鼠标触发）

1. 点击 `Set Mouse Button`。
2. 选择 `开始识别` 或 `手动输入`。
3. 若选择识别，程序会监听鼠标按钮事件（左键/右键会忽略）。
4. 识别成功后，会自动回填到输入框，可直接保存或手动修改。
5. 识别失败时，可选择重试识别，或切换为手动输入。

## 脚本说明

### 核心脚本

- `install.sh`：安装环境/依赖及可选初始化步骤
- `start_app.sh`：启动菜单栏应用
- `enable_autostart.sh`：启用 LaunchAgent 开机自启
- `disable_autostart.sh`：关闭 LaunchAgent 开机自启
- `create_launcher.sh`：创建 Applications 启动器 + 桌面符号链接
- `launch_from_desktop.sh`：桌面启动入口（静默后台启动）
- `remove_launcher.sh`：删除 Applications 启动器与桌面快捷方式
- `uninstall.sh`：卸载并清理运行环境/模型/虚拟环境
- `prepare_release.sh`：清理产物并打包发布 zip

### 卸载行为

`./uninstall.sh` 会清理：
- LaunchAgent
- 运行中的相关进程
- SenseVoice 模型缓存
- `.venv`
- 本地日志/锁文件/运行配置
- Applications/桌面启动器
- 已知应用标识的 TCC 权限项（尽力重置）

也支持连源码目录一起删除：

```bash
./uninstall.sh --delete-project-dir
```

## 键盘快捷键可用字符

### 格式

- 使用 `修饰键+主键`，例如：
  - `<ctrl>+a`
  - `<ctrl>+<left>`
  - `<cmd>+<shift>+<f8>`

### 修饰键

- `<ctrl>`
- `<alt>`
- `<cmd>`
- `<shift>`

说明：
- `<option>` 会自动规范化为 `<alt>`

### 主键

字母：
- `a` `b` `c` `d` `e` `f` `g` `h` `i` `j` `k` `l` `m` `n` `o` `p` `q` `r` `s` `t` `u` `v` `w` `x` `y` `z`

数字：
- `0 1 2 3 4 5 6 7 8 9`

符号：
- `=` `-` `[` `]` `;` `'` `\\` `,` `.` `/` `` ` ``

特殊键：
- `<space>`
- `<enter>`
- `<tab>`
- `<backspace>`
- `<delete>`
- `<esc>`
- `<left>` `<right>` `<up>` `<down>`
- `<home>` `<end>` `<pgup>` `<pgdn>`

功能键：
- `<f1>` ... `<f19>`

## 鼠标触发可用字符

支持值：
- `button2` -> `middle`
- `button3` -> `x1`
- `button4` -> `x2`
- `buttonN`（`N >= 5`，由鼠标设备决定）

重要说明：
- `left` 和 `right` 已禁用，避免和日常点击操作冲突。
- 鼠标按键编号依赖设备本身，`buttonN` 表示 macOS 上报的原始按键编号，不同鼠标可能不同。
- 推荐流程：使用 `Set Mouse Button` 后直接点击目标鼠标键，让程序自动识别并回填再保存。
- 仍保留手动输入，支持 `middle`、`x1`、`x2`、`buttonN`（`N >= 2`，且不含 `0/1`）。
- 对 Logitech MX 系列：如果侧键在 Logi Options+ 中被配置为手势或快捷键，系统可能不会上报为鼠标按钮事件。请先改为 `Generic Button`，或改用键盘触发模式。

## 权限

请给实际运行链路授予以下权限：
- 麦克风（Microphone）
- 辅助功能（Accessibility）
- 输入监控（Input Monitoring）

说明：
- 若终端启动可用但启动器不可用，请重建启动器并重新核对权限。
- 桌面快捷方式指向 `~/Applications` 同一个应用，避免 TCC 列表重复。

## GitHub 分享

生成发布包：

```bash
./prepare_release.sh
```

输出文件：
- `sensevoice-dictation-macos-release.zip`
