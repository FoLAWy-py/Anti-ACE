
# Anti-ACE

Anti-ACE 是一个 Windows 小工具，目标是通过“限制 ACE 相关守护进程的资源占用”，尽量降低其对系统的持续负载。

本项目的核心思路：
- 通过 Windows 的 **Efficiency mode / Power Throttling** 和更低的进程优先级，尽量让目标进程更“温和”地运行。
- 通过 **CPU 亲和性**（只允许使用最后一个逻辑 CPU）限制其可用计算资源。

说明：这类优化只能影响进程调度/运行方式，无法保证一定减少磁盘写入或“硬盘损伤”。是否有帮助取决于具体版本与场景，建议你以任务管理器/资源监视器的实际指标为准。

## 作用对象

当前默认处理的目标进程：
- `SGuard64.exe`
- `SGuardSvc64.exe`

程序会监控 `wegame.exe`：
- 如果 WeGame 不在运行，后台模式会自动退出（不会无限重启 WeGame）。

## 使用方式（推荐：托盘后台）

直接运行打包后的 `Anti-ACE.exe`（或在开发环境执行 `uv run antiace`）即可。

行为说明：
- 程序启动后常驻托盘。
- 托盘菜单“显示主页面”：唤出 GUI（会出现在任务栏）。
- 直接关闭 GUI 窗口：不会退出进程，而是隐藏回托盘。
- 托盘菜单“退出”：完全退出程序。

提示：部分系统/权限环境下，对目标进程应用设置可能需要“以管理员身份运行”。

## 开发环境运行

推荐使用 `uv`：

```powershell
uv run antiace
```

可选模式：

```powershell
uv run antiace --gui
uv run antiace --cli
uv run antiace --background
```

## 配置文件

程序会保存 WeGame 路径，默认位置：

- `%APPDATA%\antiace\config.json`

如果无法自动检测 WeGame，会弹出文件选择框让你手动选择 `wegame.exe`。

## 实现逻辑（工作原理）

下面以“默认后台模式（托盘常驻）”为主线，描述程序的核心运行逻辑：

1) 启动模式与入口
- 默认启动为后台模式（托盘 + 监控线程 + GUI 隐藏启动）。
- `--gui`：只显示 GUI（不启动后台监控逻辑）。
- `--cli`：命令行模式（用于无 GUI 场景/调试）。

2) WeGame 路径初始化
- 读取配置文件 `%APPDATA%\antiace\config.json`。
- 若未配置或无效：尝试自动检测（常见安装路径 + 注册表），否则弹出文件选择框让用户选择 `wegame.exe`。

3) 托盘与 GUI（单进程）
- 托盘与 Tk GUI 运行在同一进程内。
- Tk 的主循环必须在主线程运行；托盘回调发生在托盘线程，因此二者通过一个线程安全队列进行通信：
	- 托盘“显示主页面” -> 队列发送 `("ctl", "show")`，GUI 执行 `deiconify()`。
	- 托盘“退出” -> 队列发送 `("ctl", "quit")`，GUI 执行 `destroy()` 并触发整体退出。
- 关闭 GUI 窗口默认“隐藏到托盘”（`withdraw()`），不会结束进程。

4) 后台监控与优化循环
- 后台线程定期执行：
	- 检测 `wegame.exe` 是否存在：如果 WeGame 不在运行，则程序自动退出（避免长期空转）。
	- 扫描并对目标守护进程（`SGuard64.exe` / `SGuardSvc64.exe`）应用优化策略。
- 优化策略（尽力而为，可能因权限/保护进程失败）：
	- 设置更低的进程优先级
	- 启用 Windows Power Throttling / Efficiency mode（通过 WinAPI）
	- 将 CPU 亲和性限制为“最后一个逻辑 CPU”

5) 退出行为与延迟
- 监控循环采用“分段 sleep”以便尽快响应退出。
- WeGame 真正退出后，Anti-ACE 最迟约 30 秒内触发自动退出（取决于轮询间隔）。

## Bug 修复记录

### 1) WeGame 退出后 Anti-ACE 未自动退出

现象：
- 在后台模式下，即使 `wegame.exe` 已结束超过 30 秒，程序仍未自动退出。

根因：
- `run_background()` 内部使用 `state = {"value": ...}` 存储状态，但在某些分支里误写成 `state = AppState.NEED_WEGAME_PATH` / `state = AppState.READY`，把字典变量覆盖成了字符串。
- 后续监控线程尝试执行 `state["value"] = AppState.EXITING` 时抛异常，异常又被线程的 `try/except Exception: pass` 吞掉，导致监控线程静默退出，从而不再轮询 `wegame.exe`。

修复：
- 统一改为 `state["value"] = ...`，避免覆盖变量类型。
- 在检测到 WeGame 不存在时，先触发退出信号（`stop_event` / `("ctl", "quit")`），再更新状态，提升鲁棒性。

影响范围：
- 仅影响“后台模式的自动退出检测”；不影响 GUI 交互与进程优化功能本身。

## 打包（Windows / PyInstaller）

产物：`dist/Anti-ACE.exe`

1) 安装打包依赖（一次即可）

```powershell
uv pip install pyinstaller
```

2) 执行打包

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

打包参数说明：
- 程序名：`Anti-ACE`
- 图标：`icon.ico`（同时用于 EXE 与托盘图标）
- 默认使用 windowed 模式（不弹控制台窗口）
- Windows 文件属性信息（Company / Website 等）由 `version_info.txt` 写入

## 免责声明

本项目仅做进程调度层面的“资源限制/优化”，不承诺任何效果；使用本工具产生的任何风险（兼容性、性能、误报等）需自行承担。

