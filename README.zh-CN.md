# FunASR Dictation for macOS（中文说明）

FunASR Dictation 是一个基于 [Fun-ASR-Nano-2512](https://github.com/FunAudioLLM/Fun-ASR) 的 macOS 菜单栏语音输入工具：
- 按一次触发键开始录音
- 再按一次停止录音
- 使用 Fun-ASR-Nano-2512 转写
- 自动粘贴到当前输入框

相较于系统自带语音识别或常见通用工具，本应用重点优势是：
- 本地推理（无需依赖云端往返），延迟更低、响应更快
- 使用较新的开源语音模型底座（Fun-ASR），并可通过 `Update Model` 持续更新
- 在中英混合输入场景下，实测识别质量更适合高频文本输入
- 全局热键一键录音/停止并自动粘贴到任意输入框，流程更高效

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
- Python 3.11+（若缺失，安装脚本会在检测到 Homebrew 时自动安装）
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
4. 预下载 Fun-ASR-Nano-2512 + VAD 模型
5. 创建 `~/Applications` 启动器和桌面符号链接
6. 若缺少 Python 3.11+，并且系统有 Homebrew，则自动安装 Python

安装参数：
- `--no-model`
- `--no-launcher`
- `--autostart`

## 启动

```bash
./start_app.sh
```

也可以在执行 `./create_launcher.sh` 后，直接双击应用/桌面图标启动。

## Fun-ASR 调参

推荐直接在菜单 `Model Config` 中修改并保存参数（UI 方式）。

UI 保存后会自动写入 `config.toml` 持久化；手动改文件属于可选高级方式。

- `language`: `auto|zh|en|ja`（中英混说建议保持 `auto`）
- `数字与日期规范化`（`use_itn`）：开启后数字/日期格式更规整
- `合并长停顿片段`（`merge_vad`）：开启可能提升长语音速度，关闭通常断句更自然
- `hotwords`: 高频专有词（UI 支持逗号或换行输入）
- `remove_emoji`: 去除最终粘贴文本中的表情符号

本版本默认推荐参数：
- `language = "auto"`
- `sample_rate = 16000`
- `channels = 1`
- `paste_delay_ms = 20`
- `enable_beep = true`
- `use_itn = true`
- `merge_vad = false`
- `hotwords = ""`
- `remove_emoji = true`
- `batch_size_s = 0`（运行时固定内部值，UI 不提供修改）

也可以在菜单 `Model Config` 中直接修改这些运行参数（无需手动编辑文件）。

Model Config 窗口包含以下字段：
- 识别语言（`language`）
- 采样率 / 声道 / 粘贴延迟
- 高频词（`hotwords`，大文本框，支持逗号或换行）
- 录音提示音（`enable_beep`）
- 数字与日期规范化（`use_itn`）
- 合并长停顿片段（`merge_vad`）
- 过滤表情符号（`remove_emoji`）

### 输入与粘贴参数建议

- `sample_rate`：建议 `16000`；仅在麦克风驱动要求时改为 `44100/48000`。
- `channels`：建议 `1`（单声道）；仅在真实双声道采集设备上使用 `2`。
- `paste_delay_ms`：建议 `20-40`；若偶发粘贴失败，可提高到 `60`。
- 上述建议已直接显示在 Model Config 设置窗口中。

### 选项影响（非技术说明）

`数字与日期规范化`（`use_itn`）
- 开：数字、日期、单位等文本更规整。
- 关：更接近原始口语内容。

`合并长停顿片段`（`merge_vad`）
- 开：长语音场景下可能更快。
- 关：断句和标点通常更稳定。

`高频词`（`hotwords`）
- 用于人名、产品名、英文术语等高频专有词。
- UI 里可以一行一个词，也可以逗号分隔；保存时会自动规范和去重。
- 建议先从 5-50 个词开始，保持精简。

### 如何修改

1. 打开菜单 `Model Config`
2. 修改参数后点击 `Save`
3. 新参数会从下一次录音开始生效

可选（高级）：手动编辑 `config.toml`，例如：

```toml
language = "zh"
merge_vad = false
use_itn = true
hotwords = "OpenAI, GitHub, LaunchAgent"
remove_emoji = true
# 运行时兼容固定值：
batch_size_s = 0
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
- `Hotkey Settings`
- `Model Config`
- `Update Model`
- `Enable Dictation On App Start`
- `Enable Launch At Login`
- `Quit App`

### 菜单中英文名称对照

- `Toggle Dictation` / `开关语音输入`
- `Hotkey Settings` / `快捷键设置`
- `Model Config` / `模型参数设置`
- `Update Model` / `更新模型`
- `Enable Dictation On App Start` / `应用启动时自动开启听写`
- `Enable Launch At Login` / `开机自动启动`
- `Quit App` / `退出应用`

## 触发键设置流程

1. 点击 `Hotkey Settings`（系统中文下显示为“快捷键设置”）。
2. 窗口会显示当前触发模式、当前键盘快捷键、当前鼠标按键。
3. 点击 `Set Keyboard Hotkey` 或 `Set Mouse Button`：
   - 选择 `开始识别` 自动捕获；
   - 或选择 `手动输入` 直接输入按键字符。
4. 设置完成后，点击 `Use Keyboard Trigger` 或 `Use Mouse Trigger` 切换当前生效的触发方式。
5. 点击 `Done` 关闭窗口。

键盘/鼠标触发设置持久化路径：
- `~/Library/Application Support/SenseVoiceDictation/ui_settings.json`

该文件在重启应用和重启 macOS 后都会保留。

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
- `funasr_nano_runtime/`：内置 Fun-ASR 运行时代码（`model.py`、`ctc.py`、`tools/utils.py`），`Fun-ASR-Nano-2512` 必需

### 卸载行为

`./uninstall.sh` 会清理：
- LaunchAgent
- 运行中的相关进程
- Fun-ASR-Nano-2512 模型缓存（以及历史 SenseVoice 缓存，如存在）
- `.venv`
- 本地日志/锁文件/运行配置
- `~/Library/Application Support/SenseVoiceDictation/ui_settings.json` 及相关配置残留
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
- 推荐流程：打开 `Hotkey Settings` -> `Set Mouse Button`，直接点击目标鼠标键自动识别并回填后保存。
- 仍保留手动输入，支持 `middle`、`x1`、`x2`、`buttonN`（`N >= 2`，且不含 `0/1`）。
- 对 Logitech MX 系列：如果侧键在 Logi Options+ 中被配置为手势或快捷键，系统可能不会上报为鼠标按钮事件。请先改为 `Generic Button`，或改用键盘触发模式。

## 权限

请给实际运行链路授予以下权限：
- 麦克风（Microphone）
- 辅助功能（Accessibility）
- 输入监控（Input Monitoring）

说明：
- 首次授权时请务必双击 `~/Applications/FunASR Dictation.app`（或桌面快捷方式）启动，不要用 `./start_app.sh`。
- 启动器会在首次启动时主动请求麦克风/辅助功能/输入监控权限（应看到系统权限弹窗）。
- 若终端启动可用但启动器不可用，请重建启动器并重新核对权限。
- 桌面快捷方式指向 `~/Applications` 同一个应用，避免 TCC 列表重复。
- 如果首次安装后 `open -a "FunASR Dictation"` 提示找不到应用，请先执行：
  - `open "$HOME/Applications/FunASR Dictation.app"`
- 录音设备完全跟随 macOS 系统默认输入设备（程序内不做自动切换）。
- 如果热键能触发但始终没有识别文本，请优先检查麦克风权限和系统输入设备（程序会在检测到全静音录音时给出提示）。
- 如果权限列表里仍残留旧的 `SenseVoice Dictation` 条目，可执行一次旧权限重置：
  - `tccutil reset Accessibility com.lee.sensevoice.dictation.launcher`
  - `tccutil reset ListenEvent com.lee.sensevoice.dictation.launcher`
  - `tccutil reset Accessibility com.lee.sensevoice.menubar`
  - `tccutil reset ListenEvent com.lee.sensevoice.menubar`
  - 然后执行 `./create_launcher.sh`，重新打开 `FunASR Dictation.app` 并给新条目重新勾选权限。

## GitHub 分享

生成发布包：

```bash
./prepare_release.sh
```

输出文件：
- `sensevoice-dictation-macos-release.zip`
