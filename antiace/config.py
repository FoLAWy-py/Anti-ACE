from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    wegame_path: str | None = None


def _config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "antiace"
    return Path.home() / ".antiace"


def config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> AppConfig:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AppConfig()
    except Exception:
        return AppConfig()

    wegame_path = data.get("wegame_path")
    if isinstance(wegame_path, str) and wegame_path.strip():
        return AppConfig(wegame_path=wegame_path.strip())
    return AppConfig()


def save_config(cfg: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "wegame_path": cfg.wegame_path,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_valid_wegame_path(path: str | None) -> bool:
    if not path:
        return False
    try:
        p = Path(path)
    except Exception:
        return False
    if p.name.lower() != "wegame.exe":
        return False
    return p.is_file()
