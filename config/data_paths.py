"""Resolve stable, per-user writable application data paths."""

import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _user_data_dir() -> Path:
    """Return the platform's conventional per-user application data folder."""
    if sys.platform.startswith("win"):
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Ernesto" / "Journal"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Ernesto" / "Journal"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "ernesto-journal"


def data_file(name: str) -> Path:
    """Return a stable writable path, migrating an existing project data file once."""
    destination_dir = _user_data_dir()
    destination = destination_dir / name
    legacy = PROJECT_ROOT / "data" / name

    # Keep source/Linux launches on their established data store. Windows and
    # macOS use a user-writable location and copy existing data on first launch.
    if not sys.platform.startswith(("win", "darwin")):
        return legacy

    destination_dir.mkdir(parents=True, exist_ok=True)
    if not destination.exists() and legacy.is_file():
        shutil.copy2(legacy, destination)
    return destination
