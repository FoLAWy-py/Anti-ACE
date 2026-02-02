from __future__ import annotations

import os
from pathlib import Path

import psutil


def is_wegame_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name == "wegame.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def start_wegame(wegame_path: str) -> tuple[bool, str]:
    """Start wegame.exe once. Returns (ok, message)."""
    try:
        p = Path(wegame_path)
        if not p.is_file():
            return False, "wegame.exe path not found"

        # Use cwd as its folder to avoid relative resource issues.
        import subprocess

        subprocess.Popen([str(p)], cwd=str(p.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "started"
    except Exception as e:
        return False, f"start failed: {e}"


def find_wegame_exe(*, search_registry: bool = True) -> str | None:
    """Best-effort find wegame.exe in common locations and (optionally) registry."""

    candidates: list[Path] = []

    def add(p: str | None) -> None:
        if not p:
            return
        try:
            candidates.append(Path(p))
        except Exception:
            pass

    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    local_appdata = os.environ.get("LOCALAPPDATA")

    for base in [
        program_files,
        program_files_x86,
        local_appdata,
        r"C:\WeGame",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    ]:
        if not base:
            continue
        add(os.path.join(base, "WeGame", "wegame.exe"))
        add(os.path.join(base, "Tencent", "WeGame", "wegame.exe"))
        add(os.path.join(base, "Programs", "WeGame", "wegame.exe"))

    # Registry uninstall keys (best-effort)
    if search_registry and os.name == "nt":
        try:
            import winreg

            roots = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            ]

            def iter_subkeys(root, subkey_path: str):
                try:
                    with winreg.OpenKey(root, subkey_path) as key:
                        i = 0
                        while True:
                            try:
                                yield winreg.EnumKey(key, i)
                                i += 1
                            except OSError:
                                break
                except OSError:
                    return

            def read_value(root, key_path: str, name: str) -> str | None:
                try:
                    with winreg.OpenKey(root, key_path) as key:
                        val, _t = winreg.QueryValueEx(key, name)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
                except OSError:
                    return None
                return None

            for root, base_key in roots:
                for sk in iter_subkeys(root, base_key):
                    key_path = base_key + r"\\" + sk
                    display = (read_value(root, key_path, "DisplayName") or "").lower()
                    if "wegame" not in display and "腾讯" not in display:
                        continue

                    install = read_value(root, key_path, "InstallLocation")
                    if install:
                        add(os.path.join(install, "wegame.exe"))

                    icon = read_value(root, key_path, "DisplayIcon")
                    if icon:
                        # DisplayIcon can be like "C:\\Path\\wegame.exe,0"
                        icon_path = icon.split(",")[0].strip().strip('"')
                        if icon_path.lower().endswith("wegame.exe"):
                            add(icon_path)
        except Exception:
            pass

    for p in candidates:
        try:
            if p.name.lower() == "wegame.exe" and p.is_file():
                return str(p)
        except Exception:
            pass

    return None
