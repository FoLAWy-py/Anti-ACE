from __future__ import annotations

import time

import psutil

from .windows import _set_processor_affinity_last_cpu, _set_windows_efficiency_mode


class Optimizer:
    def __init__(self, *, reapply_after_seconds: int = 300):
        self._reapply_after = int(reapply_after_seconds)
        self._last_applied: dict[int, float] = {}

    def optimize_pid(self, pid: int) -> None:
        now = time.time()
        last = self._last_applied.get(int(pid), 0.0)
        if now - last < self._reapply_after:
            return

        _set_windows_efficiency_mode(int(pid))
        _set_processor_affinity_last_cpu(int(pid))
        self._last_applied[int(pid)] = now

    def optimize_by_names(self, names: list[str]) -> None:
        targets = {n.lower() for n in names}
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                pid = proc.info.get("pid")
                if pid is None:
                    continue
                if name in targets:
                    self.optimize_pid(int(pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
