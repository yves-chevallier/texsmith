"""Rendering rules exposed for ages-old imports."""

from __future__ import annotations

from texsmith.core import rules as _rules
from texsmith.core.rules import *  # noqa: F401,F403

__all__ = list(getattr(_rules, "__all__", []))
if not __all__:
    __all__ = [
        name for name in globals() if not name.startswith("_") and name not in {"_rules", "annotations"}
    ]
