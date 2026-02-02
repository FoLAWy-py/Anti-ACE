from __future__ import annotations

import time

import psutil

from .windows import _set_processor_affinity_last_cpu, _set_windows_efficiency_mode


class Optimizer:
    def __init__(self, *, reapply_after_seconds: int = 300):
        self._reapply_after = int(reapply_after_seconds)
        self._last_applied: dict[int, float] = {}

    def optimize_pid(self, pid: int) -> tuple[bool, bool, str, bool, str]:
        now = time.time()
        last = self._last_applied.get(int(pid), 0.0)
        if now - last < self._reapply_after:
            return False, False, "", False, ""

        ok_eff, msg_eff = _set_windows_efficiency_mode(int(pid))
        ok_aff, msg_aff = _set_processor_affinity_last_cpu(int(pid))
        self._last_applied[int(pid)] = now
        return True, bool(ok_eff), str(msg_eff), bool(ok_aff), str(msg_aff)

    def optimize_by_names(self, names: list[str]) -> list[tuple[str, int, bool, str, bool, str]]:
        targets = {n.lower() for n in names}
        applied_rows: list[tuple[str, int, bool, str, bool, str]] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                pid = proc.info.get("pid")
                if pid is None:
                    continue
                if name in targets:
                    did_apply, ok_eff, msg_eff, ok_aff, msg_aff = self.optimize_pid(int(pid))
                    if did_apply:
                        applied_rows.append((str(proc.info.get("name") or name), int(pid), ok_eff, msg_eff, ok_aff, msg_aff))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        return applied_rows
