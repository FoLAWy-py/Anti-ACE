from __future__ import annotations

from pathlib import Path


def pick_wegame_exe_via_gui() -> str | None:
    """Open a GUI file picker for wegame.exe and return the selected path (validated)."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        return None

    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()

    try:
        while True:
            path = filedialog.askopenfilename(
                title="Select wegame.exe",
                filetypes=[("wegame.exe", "wegame.exe"), ("Executable", "*.exe"), ("All files", "*")],
            )

            if not path:
                return None

            p = Path(path)
            if p.name.lower() == "wegame.exe" and p.is_file():
                return str(p)

            try:
                messagebox.showerror("Invalid selection", "Please select wegame.exe")
            except Exception:
                pass
    finally:
        root.destroy()
