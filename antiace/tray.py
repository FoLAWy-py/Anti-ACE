from __future__ import annotations

import threading

from .resources import resource_path


def _make_image(*, icon_path: str | None):
    # Lazy import to avoid overhead if tray isn't used.
    from PIL import Image, ImageDraw

    # Prefer the app icon (icon.ico) for tray.
    try:
        p = icon_path or resource_path("icon.ico")
        img = Image.open(p)
        img = img.convert("RGBA")
        # Pystray works best with a small RGBA image.
        img = img.resize((64, 64), Image.LANCZOS)
        return img
    except Exception:
        pass

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Simple blue rounded square with white 'U'
    draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=14, fill=(37, 99, 235, 255))
    draw.text((22, 16), "U", fill=(255, 255, 255, 255))
    return img


class TrayController:
    def __init__(self, *, on_show_main, on_exit, icon_path: str | None = None):
        self._on_show_main = on_show_main
        self._on_exit = on_exit
        self._icon_path = icon_path
        self._icon = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("显示主页面", lambda _icon, _item: self._on_show_main()),
            pystray.MenuItem("退出", lambda _icon, _item: self._on_exit()),
        )
        self._icon = pystray.Icon("antiace", _make_image(icon_path=self._icon_path), "Anti-ACE", menu=menu)

        # Run in background thread so we can keep monitor loop in main thread.
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
