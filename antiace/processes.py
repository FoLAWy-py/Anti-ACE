from __future__ import annotations

import psutil


def search_process(process_names: list[str] | tuple[str, ...]) -> list[tuple[str, int]]:
    """搜索指定名称的进程，返回匹配到的 (name, pid) 列表"""
    target_names = {name.lower() for name in process_names}
    found: list[tuple[str, int]] = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info.get("name") or ""
            pid = proc.info.get("pid")
            if pid is None:
                continue
            if name.lower() in target_names:
                found.append((name, int(pid)))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    return found
