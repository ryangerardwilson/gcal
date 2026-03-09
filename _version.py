from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _version_from_git() -> str | None:
    repo_root = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--dirty", "--always"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    if not value:
        return None
    return value[1:] if value.startswith("v") else value


def _resolve_version() -> str:
    for name in ("APP_VERSION", "VERSION"):
        value = os.environ.get(name, "").strip()
        if value:
            return value[1:] if value.startswith("v") else value
    git_version = _version_from_git()
    if git_version:
        return git_version
    return "0.0.0-dev"


__version__ = _resolve_version()
