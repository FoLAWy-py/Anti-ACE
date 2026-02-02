from __future__ import annotations

import psutil

from .processes import search_process
from .config import AppConfig, is_valid_wegame_path, load_config, save_config
from .resources import resource_path
from .tray import TrayController
from .windows import _get_system_info, _set_processor_affinity_last_cpu, _set_windows_efficiency_mode
from .wegame import find_wegame_exe, is_wegame_running


def run_gui(
    *,
    with_tray: bool = True,
    events: "queue.Queue[tuple] | None" = None,
    start_hidden: bool = False,
    close_to_tray: bool | None = None,
) -> int:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        # 极少数精简 Python 环境可能没有 Tk；此时自动降级 CLI
        from .cli import run_cli

        return run_cli()

    import os
    import threading
    import queue
    from pathlib import Path

    import webbrowser

    REPO_URL = "https://github.com/FoLAWy-py/Anti-ACE"

    target_processes = ["SGuard64.exe", "SGuardSvc64.exe"]

    # 尝试启用更清晰的字体缩放（不影响功能）
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    def _round_rect(canvas: "tk.Canvas", x1: int, y1: int, x2: int, y2: int, r: int, **kwargs):
        r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
        points = [
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _create_card(parent: "tk.Widget", *, radius: int = 14, pad: int = 12):
        """A lightweight rounded container (Canvas + inner ttk.Frame)."""
        canvas = tk.Canvas(parent, highlightthickness=0, bd=0)
        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((pad, pad), window=inner, anchor="nw")

        def redraw(_evt: object = None) -> None:
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            canvas.delete("card")
            if w <= 2 or h <= 2:
                return
            bg = style.lookup("TFrame", "background") or root.cget("background")
            canvas.configure(bg=bg)
            fill = "#FFFFFF"
            outline = "#D0D0D0"
            _round_rect(canvas, 1, 1, w - 1, h - 1, radius, fill=fill, outline=outline, width=1, tags="card")
            canvas.coords(window_id, pad, pad)
            canvas.itemconfigure(window_id, width=max(0, w - pad * 2), height=max(0, h - pad * 2))

        canvas.bind("<Configure>", redraw)
        return canvas, inner

    os_version, cpu_model = _get_system_info()

    root = tk.Tk()
    root.title("antiACE")
    # Allow a compact height to avoid unused blank areas (still resizable)
    root.geometry("840x300")
    root.minsize(840, 240)

    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except Exception:
        pass

    # Subtle app background (cards are white)
    try:
        root.configure(bg="#F3F4F6")
        style.configure("TFrame", background="#F3F4F6")
        style.configure("TLabel", background="#F3F4F6")
        style.configure("TLabelframe", background="#F3F4F6")
    except Exception:
        pass

    if events is None:
        events = queue.Queue()

    if close_to_tray is None:
        close_to_tray = bool(with_tray)

    # Set window/taskbar icon to icon.ico (best-effort).
    if os.name == "nt":
        try:
            root.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

    lang_var = tk.StringVar(value="中文")
    status_var = tk.StringVar(value="")
    wegame_status_var = tk.StringVar(value="")
    guard_status_var = tk.StringVar(value="")
    progress_var = tk.IntVar(value=0)
    total_var = tk.IntVar(value=0)
    summary_var = tk.StringVar(value="")
    info_var = tk.StringVar(value="")
    wegame_var = tk.StringVar(value="")

    wegame_state: str = "unknown"  # unknown|running|not_running|starting|start_failed
    guard_optimized_once: bool = False

    cfg = load_config()
    wegame_path_state: str | None = cfg.wegame_path if is_valid_wegame_path(cfg.wegame_path) else None

    STRINGS = {
        "zh": {
            "window_title": "AntiACE",
            "title": "进程检测与优化",
            "lang": "语言",
            "info": "系统：{os}    CPU：{cpu}",
            "summary_targets": "目标：{targets}",
            "summary_cpu": "CPU：{count} 核",
            "ready": "就绪",
            "starting": "开始…",
            "scanning": "正在扫描目标进程…",
            "not_found": "未找到目标进程",
            "found_apply": "已找到 {n} 个进程，正在应用设置…",
            "processing": "正在处理 {name}（PID {pid}）…",
            "done": "完成",
            "progress": "进度：{i}/{n}",
            "btn_start": "开始检测/应用",
            "btn_quit": "退出",
            "hint": "提示：如失败请以管理员身份运行",
            "col_proc": "进程",
            "col_pid": "PID",
            "col_eff": "效能模式",
            "col_aff": "CPU 相关性",
            "col_detail": "详情",
            "details": "详情",
            "detail_action": "详情",
            "btn_close": "关闭",
            "eff_ok": "已开启",
            "aff_ok": "已设置（仅使用 CPU {last}）",
            "failed": "失败",
            "detail_proc": "进程：{name}",
            "detail_pid": "PID：{pid}",
            "detail_eff": "效能模式：{status}",
            "detail_aff": "CPU 相关性：{status}",
            "menu_settings": "设置",
            "menu_choose_wegame": "手动选择 WeGame 路径…",
            "menu_redetect_wegame": "重新检测 WeGame 路径…",
            "wegame_path": "WeGame：{path}",
            "wegame_not_set": "未设置",
            "wegame_saved": "已保存 WeGame 路径",
            "wegame_invalid": "请选择 wegame.exe",
            "wegame_auto_found": "已自动检测到 WeGame",
            "wegame_auto_not_found": "未检测到 WeGame，请手动选择",
            "wegame_status": "WeGame 状态：{status}",
            "wegame_running": "运行中",
            "wegame_not_running": "未运行",
            "wegame_starting": "正在启动…",
            "wegame_start_failed": "启动失败",
            "wegame_unknown": "未知",
            "guard_status": "守护进程：{status}",
            "guard_waiting": "等待检测…",
            "guard_optimized": "已完成优化",
            "menu_help": "帮助",
            "menu_github": "打开 GitHub 仓库",
        },
        "en": {
            "window_title": "AntiACE Process Helper",
            "title": "Process check & tuning",
            "lang": "Language",
            "info": "OS: {os}    CPU: {cpu}",
            "summary_targets": "Targets: {targets}",
            "summary_cpu": "CPU: {count} cores",
            "ready": "Ready",
            "starting": "Starting…",
            "scanning": "Scanning target processes…",
            "not_found": "Target processes not found",
            "found_apply": "Found {n} process(es). Applying settings…",
            "processing": "Applying to {name} (PID {pid})…",
            "done": "Done",
            "progress": "Progress: {i}/{n}",
            "btn_start": "Scan & Apply",
            "btn_quit": "Quit",
            "hint": "Tip: Run as Administrator if needed",
            "col_proc": "Process",
            "col_pid": "PID",
            "col_eff": "Efficiency mode",
            "col_aff": "CPU Affinity",
            "col_detail": "Details",
            "details": "Details",
            "detail_action": "Details",
            "btn_close": "Close",
            "eff_ok": "Enabled",
            "aff_ok": "Set (CPU {last} only)",
            "failed": "Failed",
            "detail_proc": "Process: {name}",
            "detail_pid": "PID: {pid}",
            "detail_eff": "Efficiency mode: {status}",
            "detail_aff": "CPU Affinity: {status}",
            "menu_settings": "Settings",
            "menu_choose_wegame": "Choose WeGame path…",
            "menu_redetect_wegame": "Re-detect WeGame path…",
            "wegame_path": "WeGame: {path}",
            "wegame_not_set": "Not set",
            "wegame_saved": "WeGame path saved",
            "wegame_invalid": "Please select wegame.exe",
            "wegame_auto_found": "WeGame detected",
            "wegame_auto_not_found": "WeGame not found, please pick manually",
            "wegame_status": "WeGame: {status}",
            "wegame_running": "Running",
            "wegame_not_running": "Not running",
            "wegame_starting": "Starting…",
            "wegame_start_failed": "Start failed",
            "wegame_unknown": "Unknown",
            "guard_status": "Guard processes: {status}",
            "guard_waiting": "Waiting…",
            "guard_optimized": "Optimized",
            "menu_help": "Help",
            "menu_github": "Open GitHub repository",
        },
    }

    def cur_lang() -> str:
        return "en" if lang_var.get() == "English" else "zh"

    def tr(key: str, **kwargs) -> str:
        s = STRINGS[cur_lang()][key]
        return s.format(**kwargs) if kwargs else s

    def refresh_wegame_line() -> None:
        nonlocal wegame_path_state
        disp = wegame_path_state if wegame_path_state else tr("wegame_not_set")
        wegame_var.set(tr("wegame_path", path=disp))

    def choose_wegame_path() -> None:
        nonlocal wegame_path_state
        try:
            from tkinter import filedialog, messagebox
        except Exception:
            return

        path = filedialog.askopenfilename(
            parent=root,
            title="Select wegame.exe",
            filetypes=[("wegame.exe", "wegame.exe"), ("Executable", "*.exe"), ("All files", "*")],
        )
        if not path:
            return

        p = Path(path)
        if p.name.lower() != "wegame.exe" or not p.is_file():
            try:
                messagebox.showerror("Invalid selection", tr("wegame_invalid"), parent=root)
            except Exception:
                pass
            return

        wegame_path_state = str(p)
        save_config(AppConfig(wegame_path=wegame_path_state))
        refresh_wegame_line()
        set_status("ready")
        try:
            # Provide a transient confirmation.
            status_var.set(tr("wegame_saved"))
        except Exception:
            pass

    def redetect_wegame_path() -> None:
        nonlocal wegame_path_state
        auto = find_wegame_exe(search_registry=True)
        if auto and is_valid_wegame_path(auto):
            wegame_path_state = auto
            save_config(AppConfig(wegame_path=wegame_path_state))
            refresh_wegame_line()
            try:
                status_var.set(tr("wegame_auto_found"))
            except Exception:
                pass
            return

        try:
            status_var.set(tr("wegame_auto_not_found"))
        except Exception:
            pass
        choose_wegame_path()

    def open_repo(_evt: object = None) -> None:
        try:
            webbrowser.open(REPO_URL)
        except Exception:
            pass

    def refresh_status_lines() -> None:
        nonlocal wegame_state, guard_optimized_once

        if wegame_state == "running":
            wegame_status_var.set(tr("wegame_status", status=tr("wegame_running")))
        elif wegame_state == "not_running":
            wegame_status_var.set(tr("wegame_status", status=tr("wegame_not_running")))
        elif wegame_state == "starting":
            wegame_status_var.set(tr("wegame_status", status=tr("wegame_starting")))
        elif wegame_state == "start_failed":
            wegame_status_var.set(tr("wegame_status", status=tr("wegame_start_failed")))
        else:
            wegame_status_var.set(tr("wegame_status", status=tr("wegame_unknown")))

        if guard_optimized_once:
            guard_status_var.set(tr("guard_status", status=tr("guard_optimized")))
        else:
            guard_status_var.set(tr("guard_status", status=tr("guard_waiting")))

    # === Top bar card ===
    top_card, top = _create_card(root, radius=16, pad=10)
    top_card.pack(fill="x", padx=10, pady=(10, 8))
    top.columnconfigure(0, weight=1)

    # Menu bar (settings)
    menubar = tk.Menu(root)
    settings_menu = tk.Menu(menubar, tearoff=0)
    # Give initial non-empty labels to avoid a blank/buggy menu before language is applied.
    settings_menu.add_command(label=tr("menu_choose_wegame"), command=choose_wegame_path)
    settings_menu.add_command(label=tr("menu_redetect_wegame"), command=redetect_wegame_path)
    menubar.add_cascade(label=tr("menu_settings"), menu=settings_menu)

    settings_cascade_index = menubar.index("end")
    settings_choose_index = 0
    settings_redetect_index = 1

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label=tr("menu_github"), command=open_repo)
    menubar.add_cascade(label=tr("menu_help"), menu=help_menu)

    help_cascade_index = menubar.index("end")
    help_github_index = 0

    root.configure(menu=menubar)

    title = ttk.Label(top, text="", font=("Segoe UI", 14, "bold"))
    title.grid(row=0, column=0, sticky="w")

    lang_wrap = ttk.Frame(top)
    lang_wrap.grid(row=0, column=1, sticky="e")
    lang_label = ttk.Label(lang_wrap, text="")
    lang_label.pack(anchor="e")
    lang_box = ttk.Combobox(lang_wrap, width=10, state="readonly", values=("中文", "English"), textvariable=lang_var)
    lang_box.pack(anchor="e", pady=(4, 0))

    info = ttk.Label(top, textvariable=info_var)
    info.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    summary = ttk.Label(top, textvariable=summary_var)
    summary.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

    wegame_line = ttk.Label(top, textvariable=wegame_var)
    wegame_line.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))

    # Progress + status live line
    progress = ttk.Progressbar(top, mode="determinate", maximum=1, variable=progress_var)
    progress.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    status_line = ttk.Label(top, textvariable=status_var)
    status_line.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

    wegame_status_line = ttk.Label(top, textvariable=wegame_status_var)
    wegame_status_line.grid(row=6, column=0, columnspan=2, sticky="w", pady=(2, 0))

    guard_status_line = ttk.Label(top, textvariable=guard_status_var)
    guard_status_line.grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 0))

    # === Results card ===
    results_card, results = _create_card(root, radius=16, pad=10)
    results_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    results_title = ttk.Label(results, text="", font=("Segoe UI", 10, "bold"))
    results_title.pack(anchor="w", pady=(0, 6))

    table_inner = ttk.Frame(results)
    table_inner.pack(fill="both", expand=True)

    columns = ("name", "pid", "eff", "aff", "detail")
    # Start small; auto-adjust after scanning so there aren't many empty rows.
    tree = ttk.Treeview(table_inner, columns=columns, show="headings", height=3)
    tree.heading("name", text="")
    tree.heading("pid", text="")
    tree.heading("eff", text="")
    tree.heading("aff", text="")
    tree.heading("detail", text="")
    tree.column("name", width=220, anchor="w")
    tree.column("pid", width=80, anchor="e")
    tree.column("eff", width=170, anchor="w")
    tree.column("aff", width=240, anchor="w")
    tree.column("detail", width=72, anchor="center")

    vsb = ttk.Scrollbar(table_inner, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    # === Bottom action/status bar ===
    footer = ttk.Frame(root, padding=(10, 0, 10, 8))
    footer.pack(fill="x")

    # pid -> raw row data
    row_state: dict[int, dict] = {}
    cpu_count_state: int | None = None
    last_cpu_state: int | None = None
    status_state: dict[str, object] = {"key": "ready", "kwargs": {}}

    def set_status(key: str, **kwargs) -> None:
        status_state["key"] = key
        status_state["kwargs"] = kwargs
        try:
            status_var.set(tr(key, **kwargs))
        except Exception:
            # Fallback: never crash the UI due to a missing translation
            status_var.set(str(key))

    def set_table_rows(n: int) -> None:
        # Show only as many rows as needed to avoid large blanks.
        tree.configure(height=max(2, min(8, int(n))))

    def shrink_to_content() -> None:
        # Best-effort: shrink height to required size (within minsize).
        try:
            root.update_idletasks()
            req_w = root.winfo_reqwidth()
            req_h = root.winfo_reqheight()
            cur_w = root.winfo_width()
            min_w, min_h = 840, 240
            root.geometry(f"{max(cur_w, req_w, min_w)}x{max(req_h, min_h)}")
        except Exception:
            pass

    def clear_table() -> None:
        for item in tree.get_children(""):
            tree.delete(item)
        row_state.clear()
        set_table_rows(2)

    def set_running(is_running: bool) -> None:
        if is_running:
            start_btn.state(["disabled"])
        else:
            start_btn.state(["!disabled"])

    def worker_scan_apply() -> None:
        try:
            events.put(("status", "scanning"))
            found = search_process(target_processes)
            events.put(("found", found))
            if not found:
                events.put(("done",))
                return

            cpu_count = psutil.cpu_count(logical=True) or os.cpu_count() or 0
            last_cpu = (cpu_count - 1) if cpu_count > 0 else None
            events.put(("cpu", cpu_count, last_cpu))
            events.put(("status", "found_apply", len(found)))

            for idx, (name, pid) in enumerate(found, start=1):
                events.put(("status", "processing", name, pid))

                ok_eff, msg_eff = _set_windows_efficiency_mode(pid)
                ok_aff, msg_aff = _set_processor_affinity_last_cpu(pid)

                events.put(("row_update", name, pid, ok_eff, msg_eff, ok_aff, msg_aff, idx, len(found)))

            events.put(("status", "done"))
        finally:
            events.put(("done",))

    def start() -> None:
        clear_table()
        set_status("starting")
        summary_var.set(tr("summary_targets", targets=", ".join(target_processes)))
        progress_var.set(0)
        total_var.set(0)
        progress.configure(mode="indeterminate")
        progress.start(10)
        set_running(True)

        t = threading.Thread(target=worker_scan_apply, daemon=True)
        t.start()

    def poll_events() -> None:
        nonlocal cpu_count_state, last_cpu_state
        nonlocal wegame_state, guard_optimized_once
        try:
            while True:
                ev = events.get_nowait()
                kind = ev[0]
                if kind == "bg_found":
                    try:
                        found = ev[1]
                        total_var.set(len(found) if found else 0)
                        # Keep a minimum height so the list is visible.
                        set_table_rows(len(found) if found else 2)
                        shrink_to_content()
                    except Exception:
                        pass
                    continue
                if kind == "wegame":
                    wegame_state = str(ev[1]) if len(ev) > 1 else "unknown"
                    refresh_status_lines()
                    continue
                if kind == "guard":
                    action = str(ev[1]) if len(ev) > 1 else ""
                    if action == "optimized":
                        guard_optimized_once = True
                        refresh_status_lines()
                    continue
                if kind == "ctl":
                    action = str(ev[1]) if len(ev) > 1 else ""
                    if action == "show":
                        try:
                            root.deiconify()
                            root.lift()
                            root.focus_force()
                        except Exception:
                            pass
                    elif action == "hide":
                        try:
                            root.withdraw()
                        except Exception:
                            pass
                    elif action == "quit":
                        try:
                            root.destroy()
                        except Exception:
                            pass
                    continue
                if kind == "tray_show":
                    try:
                        root.deiconify()
                        root.lift()
                        root.focus_force()
                    except Exception:
                        pass
                    continue
                if kind == "tray_exit":
                    try:
                        root.destroy()
                    except Exception:
                        pass
                    continue
                if kind == "status":
                    code = ev[1]
                    if code == "scanning":
                        set_status("scanning")
                    elif code == "found_apply":
                        set_status("found_apply", n=int(ev[2]))
                    elif code == "processing":
                        set_status("processing", name=ev[2], pid=int(ev[3]))
                    elif code == "done":
                        set_status("done")
                    else:
                        status_var.set(str(code))
                elif kind == "cpu":
                    cpu_count_state = int(ev[1])
                    last_cpu_state = int(ev[2]) if ev[2] is not None else None
                    summary_var.set(
                        tr("summary_targets", targets=", ".join(target_processes))
                        + "    "
                        + tr("summary_cpu", count=cpu_count_state)
                    )
                elif kind == "found":
                    found = ev[1]
                    total_var.set(len(found))
                    set_table_rows(len(found) if found else 2)
                    progress.stop()
                    progress.configure(mode="determinate", maximum=max(1, len(found)))
                    progress_var.set(0)
                    if not found:
                        summary_var.set(tr("summary_targets", targets=", ".join(target_processes)))
                        set_status("not_found")
                        shrink_to_content()
                elif kind == "row_update":
                    _, name, pid, ok_eff, msg_eff, ok_aff, msg_aff, idx, total = ev
                    progress_var.set(idx)
                    iid = f"{pid}"

                    last_cpu_disp = last_cpu_state if last_cpu_state is not None else "?"
                    eff_text = tr("eff_ok") if ok_eff else tr("failed")
                    aff_text = tr("aff_ok", last=last_cpu_disp) if ok_aff else tr("failed")
                    detail_text = tr("detail_action")

                    if tree.exists(iid):
                        tree.item(iid, values=(name, pid, eff_text, aff_text, detail_text))
                    else:
                        tree.insert("", "end", iid=iid, values=(name, pid, eff_text, aff_text, detail_text))
                    row_state[int(pid)] = {
                        "name": name,
                        "pid": int(pid),
                        "ok_eff": bool(ok_eff),
                        "msg_eff": str(msg_eff),
                        "ok_aff": bool(ok_aff),
                        "msg_aff": str(msg_aff),
                    }
                    set_status("progress", i=int(idx), n=int(total))
                elif kind == "done":
                    progress.stop()
                    set_running(False)
                    shrink_to_content()
        except queue.Empty:
            pass

        root.after(100, poll_events)

    tray: TrayController | None = None
    if with_tray:
        def on_show_main() -> None:
            # NOTE: pystray callbacks happen on tray thread; marshal into Tk thread via queue.
            events.put(("tray_show",))

        def on_exit() -> None:
            events.put(("tray_exit",))

        tray = TrayController(on_show_main=on_show_main, on_exit=on_exit, icon_path=resource_path("icon.ico"))
        tray.start()

        def on_close_to_tray() -> None:
            try:
                root.withdraw()
            except Exception:
                pass

        if close_to_tray:
            root.protocol("WM_DELETE_WINDOW", on_close_to_tray)

    if close_to_tray and not with_tray:
        # Embedded mode (tray is managed externally): still hide window on close.
        def on_close_to_tray_external() -> None:
            try:
                root.withdraw()
            except Exception:
                pass

        root.protocol("WM_DELETE_WINDOW", on_close_to_tray_external)

    def show_details(pid: int) -> None:
        row = row_state.get(int(pid))
        if not row:
            return

        last_cpu_disp = last_cpu_state if last_cpu_state is not None else "?"
        eff_status = tr("eff_ok") if row["ok_eff"] else tr("failed")
        aff_status = tr("aff_ok", last=last_cpu_disp) if row["ok_aff"] else tr("failed")
        text = (
            tr("detail_proc", name=row["name"]) + "\n"
            + tr("detail_pid", pid=row["pid"]) + "\n\n"
            + tr("detail_eff", status=eff_status)
            + "\n"
            + row["msg_eff"]
            + "\n\n"
            + tr("detail_aff", status=aff_status)
            + "\n"
            + row["msg_aff"]
            + "\n"
        )

        win = tk.Toplevel(root)
        win.title(tr("details"))
        win.transient(root)
        win.grab_set()
        win.minsize(520, 240)

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        lbl = ttk.Label(frame, text=f"{row['name']}  (PID {row['pid']})", font=("Segoe UI", 10, "bold"))
        lbl.pack(anchor="w")

        # Adapt height to content to reduce empty space
        line_count = max(8, min(18, text.count("\n") + 2))
        txt = tk.Text(frame, height=line_count, wrap="word")
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        sb = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True, pady=(8, 0))
        sb.pack(side="right", fill="y", pady=(8, 0))

        btns = ttk.Frame(win, padding=(12, 0, 12, 12))
        btns.pack(fill="x")
        ttk.Button(btns, text=tr("btn_close"), command=win.destroy).pack(side="right")

    def on_tree_click(event: "tk.Event") -> None:
        row_id = tree.identify_row(event.y)
        col = tree.identify_column(event.x)
        if not row_id or not col:
            return
        # columns are 1-based: #1 name, #2 pid, #3 eff, #4 aff, #5 detail
        if col == "#5":
            try:
                pid = int(row_id)
            except ValueError:
                return
            show_details(pid)

    tree.bind("<Button-1>", on_tree_click)

    start_btn = ttk.Button(footer, text="", command=start)
    start_btn.pack(side="left")

    quit_btn = ttk.Button(footer, text="", command=root.destroy)
    quit_btn.pack(side="right")

    hint = ttk.Label(footer, text="")
    hint.pack(side="right", padx=(0, 12))

    def apply_language(_evt: object = None) -> None:
        def refresh_summary() -> None:
            # Always recompute summary so translation updates immediately.
            if cpu_count_state is not None:
                summary_var.set(
                    tr("summary_targets", targets=", ".join(target_processes))
                    + "    "
                    + tr("summary_cpu", count=cpu_count_state)
                )
            else:
                summary_var.set(tr("summary_targets", targets=", ".join(target_processes)))

        root.title(tr("window_title"))
        title.configure(text=tr("title"))
        lang_label.configure(text=tr("lang"))
        info_var.set(tr("info", os=os_version, cpu=cpu_model))
        results_title.configure(text=tr("summary_targets", targets=", ".join(target_processes)))
        start_btn.configure(text=tr("btn_start"))
        quit_btn.configure(text=tr("btn_quit"))
        hint.configure(text=tr("hint"))

        # Keep status lines consistent when switching language.
        refresh_status_lines()

        # Menu translation
        try:
            if settings_cascade_index is not None:
                menubar.entryconfig(settings_cascade_index, label=tr("menu_settings"))
            if help_cascade_index is not None:
                menubar.entryconfig(help_cascade_index, label=tr("menu_help"))
            settings_menu.entryconfig(settings_choose_index, label=tr("menu_choose_wegame"))
            settings_menu.entryconfig(settings_redetect_index, label=tr("menu_redetect_wegame"))
            help_menu.entryconfig(help_github_index, label=tr("menu_github"))
        except Exception:
            pass

        tree.heading("name", text=tr("col_proc"))
        tree.heading("pid", text=tr("col_pid"))
        tree.heading("eff", text=tr("col_eff"))
        tree.heading("aff", text=tr("col_aff"))
        tree.heading("detail", text=tr("col_detail"))

        refresh_summary()
        refresh_wegame_line()

        # Re-render existing rows under the new language
        last_cpu_disp = last_cpu_state if last_cpu_state is not None else "?"
        for pid, row in row_state.items():
            eff_text = tr("eff_ok") if row["ok_eff"] else tr("failed")
            aff_text = tr("aff_ok", last=last_cpu_disp) if row["ok_aff"] else tr("failed")
            detail_text = tr("detail_action")
            iid = str(pid)
            if tree.exists(iid):
                tree.item(iid, values=(row["name"], pid, eff_text, aff_text, detail_text))

        # Re-render current status text under the new language
        try:
            key = str(status_state.get("key", "ready"))
            kwargs = dict(status_state.get("kwargs", {}))
        except Exception:
            key, kwargs = "ready", {}
        set_status(key, **kwargs)

    lang_box.bind("<<ComboboxSelected>>", apply_language)
    apply_language()

    # Initialize status lines (best-effort when running GUI-only mode).
    try:
        wegame_state = "running" if is_wegame_running() else "not_running"
    except Exception:
        wegame_state = "unknown"
    refresh_status_lines()

    refresh_wegame_line()

    if start_hidden:
        try:
            root.withdraw()
        except Exception:
            pass

    root.after(100, poll_events)
    # 启动时自动跑一次，更像“监控面板”
    root.after(200, start)
    root.mainloop()

    if tray is not None:
        try:
            tray.stop()
        except Exception:
            pass
    return 0
