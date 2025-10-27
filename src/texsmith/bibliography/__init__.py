"""Bibliography helpers exposed for public consumption."""
# pyright: reportUnsupportedDunderAll=false

from __future__ import annotations

from texsmith.core import bibliography as _bibliography
from texsmith.core.bibliography import *


__all__ = list(getattr(_bibliography, "__all__", []))
if not __all__:
    __all__ = [
        name
        for name in globals()
        if not name.startswith("_") and name not in {"_bibliography", "annotations"}
    ]
