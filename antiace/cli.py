from __future__ import annotations

from .processes import search_process
from .windows import _set_processor_affinity_last_cpu, _set_windows_efficiency_mode


def run_cli() -> int:
    target_processes = ["SGuard64.exe", "SGuardSvc64.exe"]
    found_processes = search_process(target_processes)

    if not found_processes:
        print("not found")
        return 1

    print("find")
    # 输出所有匹配到的 PID（可能同时存在多个）
    print(" ".join(str(pid) for _, pid in found_processes))

    for name, pid in found_processes:
        ok, msg = _set_windows_efficiency_mode(pid)
        status = "ok" if ok else "failed"
        print(f"{name} pid={pid} efficiency={status} ({msg})")

        ok, msg = _set_processor_affinity_last_cpu(pid)
        status = "ok" if ok else "failed"
        print(f"{name} pid={pid} affinity={status} ({msg})")

    return 0
