from __future__ import annotations

import psutil


def _get_system_info() -> tuple[str, str]:
    """Return (os_version, cpu_model) in a best-effort way."""
    import os
    import platform
    import sys

    os_version = platform.platform()
    cpu_model = ""

    if os.name == "nt":
        try:
            win = platform.win32_ver()
            # win: (release, version, csd, ptype)
            if win and (win[0] or win[1]):
                build = ""
                try:
                    build = str(getattr(sys.getwindowsversion(), "build", "")).strip()
                except Exception:
                    build = ""
                os_version = f"Windows {win[0]} {win[1]}".strip()
                if build:
                    os_version = f"{os_version} (Build {build})"
        except Exception:
            pass

        # Prefer the registry string (usually shows Intel i9 / AMD Ryzen etc.)
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                cpu_model = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except Exception:
            cpu_model = ""

        # Fallback: PowerShell CIM (no extra deps)
        if not cpu_model:
            try:
                import subprocess

                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
                ]
                out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
                if out:
                    cpu_model = out
            except Exception:
                pass

    # Last fallback (often empty on Windows)
    if not cpu_model:
        import platform

        cpu_model = platform.processor() or ""

    if not cpu_model:
        cpu_model = "Unknown CPU"

    return os_version, cpu_model


def _set_windows_efficiency_mode(pid: int) -> tuple[bool, str]:
    """尽力将指定 PID 的进程设置为 Efficiency mode。

    近似实现：
    - 降低进程优先级（Low / Idle）
    - 启用 Process Power Throttling（Execution Speed throttling / EcoQoS 相关）

    说明：某些受保护/高权限进程可能会失败（Access Denied）。
    """
    import os
    import ctypes
    from ctypes import wintypes

    if os.name != "nt":
        return False, "Not running on Windows"

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PROCESS_SET_INFORMATION = 0x0200
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    IDLE_PRIORITY_CLASS = 0x00000040

    # https://learn.microsoft.com/windows/win32/api/processthreadsapi/ne-processthreadsapi-process_information_class
    # SetProcessInformation(..., ProcessPowerThrottling, ...)
    ProcessPowerThrottling = 4
    PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
    POWER_THROTTLING_EXECUTION_SPEED = 0x1

    class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
        _fields_ = [
            ("Version", wintypes.ULONG),
            ("ControlMask", wintypes.ULONG),
            ("StateMask", wintypes.ULONG),
        ]

    OpenProcess = kernel32.OpenProcess
    OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    OpenProcess.restype = wintypes.HANDLE

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    SetPriorityClass = kernel32.SetPriorityClass
    SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    SetPriorityClass.restype = wintypes.BOOL

    # SetProcessInformation exists on Windows 8+.
    try:
        SetProcessInformation = kernel32.SetProcessInformation
    except AttributeError:
        return False, "SetProcessInformation not available on this Windows version"
    SetProcessInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.INT,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    SetProcessInformation.restype = wintypes.BOOL

    desired_access = PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION
    handle = OpenProcess(desired_access, False, int(pid))
    if not handle:
        return False, f"OpenProcess failed (pid={pid}) errno={ctypes.get_last_error()}"

    try:
        ok_priority = bool(SetPriorityClass(handle, IDLE_PRIORITY_CLASS))
        if not ok_priority:
            return False, f"SetPriorityClass failed errno={ctypes.get_last_error()}"

        state = PROCESS_POWER_THROTTLING_STATE(
            Version=PROCESS_POWER_THROTTLING_CURRENT_VERSION,
            ControlMask=POWER_THROTTLING_EXECUTION_SPEED,
            StateMask=POWER_THROTTLING_EXECUTION_SPEED,
        )
        ok_throttle = bool(
            SetProcessInformation(
                handle,
                ProcessPowerThrottling,
                ctypes.byref(state),
                ctypes.sizeof(state),
            )
        )
        if not ok_throttle:
            return False, f"SetProcessInformation(ProcessPowerThrottling) failed errno={ctypes.get_last_error()}"

        return True, "ok (priority=low/idle + power_throttling=execution_speed)"
    finally:
        CloseHandle(handle)


def _set_processor_affinity_last_cpu(pid: int) -> tuple[bool, str]:
    """将指定 PID 的 CPU 亲和性限制为“最后一个逻辑 CPU”。

    例：逻辑 CPU 数为 32，则仅允许使用 CPU 31。
    """
    import os

    cpu_count = psutil.cpu_count(logical=True) or os.cpu_count() or 0
    if cpu_count <= 0:
        return False, "Cannot determine logical CPU count"

    last_cpu = cpu_count - 1

    try:
        proc = psutil.Process(int(pid))
        proc.cpu_affinity([last_cpu])
        return True, f"ok (cpu_count={cpu_count} affinity=[{last_cpu}])"
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return False, f"{type(e).__name__}: {e}"
