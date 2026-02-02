from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """Return an absolute path to a resource.

    - In development: resolve relative to repo root.
    - In PyInstaller: resolve relative to sys._MEIPASS.
    """

    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base) / relative_path)

    # antiace/resources.py -> antiace/ -> repo root
    return str(Path(__file__).resolve().parent.parent / relative_path)
