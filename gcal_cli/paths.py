from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / "gcal"
    return Path("~/.config/gcal").expanduser()


def config_file() -> Path:
    return config_dir() / "config.json"


def data_dir() -> Path:
    xdg_data_home = os.getenv("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "gcal"
    return Path("~/.local/share/gcal").expanduser()


def tokens_dir() -> Path:
    return data_dir() / "tokens"


def ensure_dirs() -> None:
    for directory in (config_dir(), data_dir(), tokens_dir()):
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError:
            pass
