"""Disk cache: one directory, pickle in, pickle out."""
import os
import pickle
import sys
from pathlib import Path


def cache_dir() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches"
    else:
        root = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    d = Path(root) / "glyph-sleuth"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load(name, default=None):
    try:
        with open(cache_dir() / name, "rb") as fh:
            return pickle.load(fh)
    except Exception:
        # ponytail: any failure (missing, truncated, version skew) just means "rebuild".
        return default


def save(name, obj):
    path = cache_dir() / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)
