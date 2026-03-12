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
- 在 `~/Applications` 生成图形化卸载器
- 桌面快捷方式是可选功能，且会指向同一应用的符号链接（避免重复权限条目）
- 支持打包为 DMG，方便普通用户安装（安装时下载独立 Python、依赖和最新模型）
- 安装与卸载使用原生 macOS 进度窗口，不再弹出终端
- 一键卸载并清理环境

## 环境要求

- macOS 11+
- Python 3.11+（仅源码安装 `./install.sh` 需要）
- Xcode Command Line Tools（仅源码安装且没有内置 launcher 二进制时，才需要 `clang`）

可选：
- `ffmpeg`（当前流程不是必需）

## DMG 安装

DMG 安装器面向普通用户：
- DMG 本身不包含模型缓存
- 不需要 Homebrew，也不需要系统预装 Python
- 安装过程中会下载独立 Python runtime、Python 依赖和最新版模型
- 程序运行文件会复制到 `~/Library/Application Support/FunASRDictation/app`
- 独立 Python runtime 会放在 `~/Library/Application Support/FunASRDictation/python-runtime`
- 最终可点击应用会生成在 `~/Applications/FunASR Dictation.app`
- 同时会生成 `~/Applications/Uninstall FunASR Dictation.app` 图形化卸载器

本地构建安装用 DMG：

```bash
./build_dmg.sh
```

产物：

```bash
./funasr-dictation-installer-2.1.9.dmg
```

打开 DMG 后，双击 `Install FunASR Dictation.app` 即可。安装器会弹出原生 macOS 安装窗口，实时显示进度与日志，下载独立 Python runtime、安装依赖、下载最新模型，然后基于本项目稳定的 TCC 身份重建最终启动器。

安装完成后：
- 安装器不再自动拉起应用
- 你可以按需点击 `创建桌面快捷方式`
- 安装器会提示：桌面快捷方式在卸载时，macOS 可能要求你手动删除
- 然后再点击 `打开应用`，或手动双击 `~/Applications/FunASR Dictation.app`

这样可以避免在安装器窗口仍处于前台时触发系统权限弹窗，从而绕开 macOS “隐私与安全性”扩展偶发崩溃的问题。

## 安装

```bash
./install.sh
```

默认安装行为：
1. 创建 `.venv`
2. 安装 Python 依赖（`requirements.txt`）
3. 若不存在则从 `config.example.toml` 生成 `config.toml`
4. 预下载 Fun-ASR-Nano-2512 + VAD 模型
5. 创建 `~/Applications` 启动器
6. 桌面快捷方式默认不创建，可稍后执行 `./create_desktop_shortcut.sh` 按需创建
6. 若缺少 Python 3.11+，并且系统有 Homebrew，则自动安装 Python

安装参数：
- `--no-model`
- `--no-launcher`
- `--autostart`

## 启动

```bash
./start_app.sh
```

也可以在执行 `./create_launcher.sh` 后直接双击应用图标启动；如果还需要桌面快捷方式，再执行 `./create_desktop_shortcut.sh`。

如果使用 DMG 安装，请直接双击 DMG 内的 `Install FunASR Dictation.app`，不需要手动执行 `install.sh`。

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
- `idle_unload_seconds = 300`
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
- 空闲卸载模型秒数（`idle_unload_seconds`）
- 高频词（`hotwords`，大文本框，支持逗号或换行）
- 录音提示音（`enable_beep`）
- 数字与日期规范化（`use_itn`）
- 合并长停顿片段（`merge_vad`）
- 过滤表情符号（`remove_emoji`）

### 输入与粘贴参数建议

- `sample_rate`：建议 `16000`；仅在麦克风驱动要求时改为 `44100/48000`。
- `channels`：建议 `1`（单声道）；仅在真实双声道采集设备上使用 `2`。
- `paste_delay_ms`：建议 `20-40`；若偶发粘贴失败，可提高到 `60`。
- `idle_unload_seconds`：建议 `300`；设为 `0` 表示永不进行空闲卸载。数值越小，空闲内存释放越积极，但空闲后下一次使用会重新加载模型。
- 上述建议已直接显示在 Model Config 设置窗口中。

### 选项影响（非技术说明）

`数字与日期规范化`（`use_itn`）
- 开：数字、日期、单位等文本更规整。
- 关：更接近原始口语内容。

`合并长停顿片段`（`merge_vad`）
- 开：长语音场景下可能更快。
- 关：断句和标点通常更稳定。

`空闲卸载模型秒数`（`idle_unload_seconds`）
- `0`：只要听写保持开启，就永不卸载 ASR 模型。
- `300`（推荐）：空闲 5 分钟后释放模型内存，下次使用时自动重新加载。
- 更小的数值：更省内存，但空闲后第一次使用会等待模型加载。

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
- `create_launcher.sh`：创建 Applications 启动器
- `create_desktop_shortcut.sh`：创建可选的桌面快捷方式符号链接
- `create_uninstaller.sh`：创建 Applications 图形化卸载器
- `launch_from_desktop.sh`：桌面启动入口（静默后台启动）
- `remove_launcher.sh`：删除 Applications 启动器与桌面快捷方式
- `uninstall.sh`：卸载并清理运行环境/模型/虚拟环境
- `prepare_release.sh`：清理产物并打包发布 zip
- `build_dmg.sh`：构建给终端用户使用的 DMG 安装包
- `install_from_dmg.command`：DMG 内部使用的安装入口脚本
- `download_python_runtime.sh`：为 DMG 安装下载并校验固定版本的独立 Python runtime
- `task_runner/TaskProgressApp.m`：安装器/卸载器共用的原生 macOS 任务进度窗口
- `launcher/FunASRLauncher.c`：launcher 源码，负责申请 TCC 权限并从 Application Support 读取真实运行目录
- `funasr_nano_runtime/`：内置 Fun-ASR 运行时代码（`model.py`、`ctc.py`、`tools/utils.py`），`Fun-ASR-Nano-2512` 必需

### 卸载行为

`./uninstall.sh` 会清理：
- LaunchAgent
- 运行中的相关进程
- Fun-ASR-Nano-2512 模型缓存（以及历史 SenseVoice 缓存，如存在）
- `.venv`
- 本地日志/锁文件/运行配置
- `~/Library/Application Support/SenseVoiceDictation/ui_settings.json` 及相关配置残留
- Applications/桌面启动器与图形化卸载器
- `~/Library/Application Support/FunASRDictation` 下的 DMG 安装运行目录
- 已知应用标识的 TCC 权限项（尽力重置）

桌面快捷方式删除是 best-effort：
- 如果 macOS 阻止自动删除桌面快捷方式，卸载仍会继续完成
- 卸载器会明确提醒你手动从桌面删除该快捷方式

也支持连源码目录或 DMG 运行目录一起删除：

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
- 首次授权时请务必双击 `~/Applications/FunASR Dictation.app`（如果你创建了桌面快捷方式，也可双击它）启动，不要用 `./start_app.sh`。
- 启动器会在首次启动时主动请求麦克风/辅助功能/输入监控权限（应看到系统权限弹窗）。
- 若终端启动可用但启动器不可用，请重建启动器并重新核对权限。
- 如果创建了桌面快捷方式，它会指向 `~/Applications` 同一个应用，避免 TCC 列表重复。
- 如果首次安装后 `open -a "FunASR Dictation"` 提示找不到应用，请先执行：
  - `open "$HOME/Applications/FunASR Dictation.app"`
- 录音设备完全跟随 macOS 系统默认输入设备（程序内不做自动切换）。
- 如果热键能触发但始终没有识别文本，请优先检查麦克风权限和系统输入设备（程序会在检测到全静音录音时给出提示）。
- 权限身份迁移（仅在权限反复失效时执行一次）：
  - `./create_launcher.sh --force-rebuild`
  - 重新打开 `FunASR Dictation.app` 并重新授权一次。
  - 启动器现在固定使用单一 Bundle ID（`com.lee.sensevoice.dictation.launcher`），并自动清理历史 `com.lee.funasr.dictation.launcher` 残留 TCC 记录。

## GitHub 分享

生成发布包：

```bash
./prepare_release.sh
```

输出文件：
- `sensevoice-dictation-macos-release.zip`
