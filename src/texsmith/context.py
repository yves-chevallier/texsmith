"""Context primitives preserved at the legacy import location."""
# pyright: reportUnsupportedDunderAll=false

from __future__ import annotations

from texsmith.core import context as _context
from texsmith.core.context import *


__all__ = list(getattr(_context, "__all__", []))
if not __all__:
    __all__ = [
        name
        for name in globals()
        if not name.startswith("_") and name not in {"_context", "annotations"}
    ]
