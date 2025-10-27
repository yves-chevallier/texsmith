"""Utility helpers retained under the legacy module name."""

from __future__ import annotations

from texsmith.core import utils as _utils
from texsmith.core.utils import *  # noqa: F401,F403

__all__ = list(getattr(_utils, "__all__", []))
if not __all__:
    __all__ = [
        name for name in globals() if not name.startswith("_") and name not in {"_utils", "annotations"}
    ]
