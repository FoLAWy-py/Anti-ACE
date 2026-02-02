from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import queue

import psutil

from .config import AppConfig, is_valid_wegame_path, load_config, save_config
from .optimizer import Optimizer
from .picker import pick_wegame_exe_via_gui
from .resources import resource_path
from .tray import TrayController
from .wegame import find_wegame_exe, is_wegame_running, start_wegame


class AppState:
    INIT = "INIT"
    NEED_WEGAME_PATH = "NEED_WEGAME_PATH"
    READY = "READY"
    EXITING = "EXITING"


def _spawn_main_gui() -> None:
    # Launch a separate process so Tk doesn't interfere with tray/monitor.
    try:
        if getattr(sys, "frozen", False):
            # Frozen: sys.executable is our packaged exe.
            cmd = [sys.executable, "--gui", "--no-tray"]
        else:
            # Dev: run module entrypoint.
            cmd = [sys.executable, "-m", "antiace", "--gui", "--no-tray"]

        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def run_background() -> int:
    state = {"value": AppState.INIT}
    stop_event = threading.Event()

    # GUI control/events queue (consumed by Tk thread).
    gui_events: "queue.Queue[tuple]" = queue.Queue()

    cfg = load_config()

    # === State: ensure wegame path ===
    if not is_valid_wegame_path(cfg.wegame_path):
        state["value"] = AppState.NEED_WEGAME_PATH

        auto = find_wegame_exe(search_registry=True)
        if auto:
            cfg = AppConfig(wegame_path=auto)
            save_config(cfg)
        else:
            picked = pick_wegame_exe_via_gui()
            if not is_valid_wegame_path(picked):
                # User cancelled or invalid selection.
                return 1
            cfg = AppConfig(wegame_path=str(picked))
            save_config(cfg)

    # === State: READY (tray + monitor) ===
    state["value"] = AppState.READY

    # Publish initial WeGame status to GUI.
    try:
        gui_events.put(("wegame", "running" if is_wegame_running() else "not_running"))
    except Exception:
        pass

    # Start wegame once if not running.
    started = False
    if not is_wegame_running() and cfg.wegame_path:
        try:
            gui_events.put(("wegame", "starting"))
        except Exception:
            pass
        ok, _msg = start_wegame(cfg.wegame_path)
        started = bool(ok)
        try:
            gui_events.put(("wegame", "running" if started else "start_failed"))
        except Exception:
            pass

    # If we attempted to start it, give it a short grace period to appear.
    if started:
        deadline = time.time() + 10
        while time.time() < deadline and not is_wegame_running() and not stop_event.is_set():
            time.sleep(0.25)
        try:
            gui_events.put(("wegame", "running" if is_wegame_running() else "not_running"))
        except Exception:
            pass

    optimizer = Optimizer(reapply_after_seconds=300)
    # Only optimize the guard processes; wegame.exe is monitored but not tuned.
    target_names = ["SGuard64.exe", "SGuardSvc64.exe"]

    # Publish CPU info for UI display (core count + last logical CPU index).
    try:
        cpu_count = psutil.cpu_count(logical=True) or os.cpu_count() or 0
        last_cpu = (cpu_count - 1) if cpu_count and cpu_count > 0 else None
        gui_events.put(("cpu", int(cpu_count), last_cpu))
    except Exception:
        pass

    def on_show_main() -> None:
        gui_events.put(("ctl", "show"))

    def on_exit() -> None:
        stop_event.set()
        gui_events.put(("ctl", "quit"))

    tray = TrayController(on_show_main=on_show_main, on_exit=on_exit, icon_path=resource_path("icon.ico"))
    tray.start()

    def monitor_loop() -> None:
        """Background monitor loop; runs while Tk mainloop is active."""
        try:
            optimized_once = False
            while not stop_event.is_set():
                if not is_wegame_running():
                    # If wegame is gone, we exit. We do NOT restart endlessly.
                    stop_event.set()
                    gui_events.put(("ctl", "quit"))
                    state["value"] = AppState.EXITING
                    break

                rows = optimizer.optimize_by_names(target_names)
                if rows:
                    # Ensure the table can resize/update without relying on GUI scan.
                    try:
                        gui_events.put(("bg_found", [(name, pid) for (name, pid, *_rest) in rows]))
                    except Exception:
                        pass

                    for idx, (name, pid, ok_eff, msg_eff, ok_aff, msg_aff) in enumerate(rows, start=1):
                        try:
                            gui_events.put(("row_update", name, pid, ok_eff, msg_eff, ok_aff, msg_aff, idx, len(rows)))
                        except Exception:
                            pass

                    if not optimized_once:
                        optimized_once = True
                        try:
                            gui_events.put(("guard", "optimized"))
                        except Exception:
                            pass

                # Sleep in small increments so exit is responsive.
                for _ in range(30):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
        except Exception:
            # Never crash the app due to monitor issues.
            pass

    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()

    try:
        # Run the GUI in the main thread (Tk requirement on Windows).
        from .gui import run_gui

        return run_gui(with_tray=False, events=gui_events, start_hidden=True, close_to_tray=True)
    finally:
        stop_event.set()
        tray.stop()
        try:
            t.join(timeout=2)
        except Exception:
            pass

    return 0
