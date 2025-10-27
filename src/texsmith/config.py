"""Configuration objects reachable from the historic namespace."""

from __future__ import annotations

from texsmith.core import config as _config
from texsmith.core.config import *  # noqa: F401,F403

__all__ = list(getattr(_config, "__all__", []))
if not __all__:
    __all__ = [
        name
        for name in globals()
        if not name.startswith("_") and name not in {"_config", "annotations"}
    ]
