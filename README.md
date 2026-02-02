
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

