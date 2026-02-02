from __future__ import annotations

import argparse

# Support execution as a plain script file path (some runners do this),
# where Python would otherwise set sys.path[0] to the package directory
# and make `import antiace` fail.
if __package__ in (None, ""):
    import os
    import sys

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from antiace.cli import run_cli
from antiace.gui import run_gui
from antiace.app import run_background


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--background", action="store_true", help="Run in background mode (tray + monitor). Default.")
    mode.add_argument("--gui", action="store_true", help="Show the main GUI page")
    mode.add_argument("--cli", action="store_true", help="Run in CLI mode (no Tkinter GUI)")
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="(GUI mode) Do not create an extra tray icon (used when opened from background tray)",
    )
    args = parser.parse_args()

    if args.cli:
        return run_cli()
    if args.gui:
        return run_gui(with_tray=not args.no_tray)

    # Default: background
    return run_background()


if __name__ == "__main__":
    raise SystemExit(main())
