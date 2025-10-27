"""Exception hierarchy kept available for existing importers."""
# pyright: reportUnsupportedDunderAll=false

from __future__ import annotations

from texsmith.core import exceptions as _exceptions
from texsmith.core.exceptions import *


__all__ = list(getattr(_exceptions, "__all__", []))
if not __all__:
    __all__ = [
        name
        for name in globals()
        if not name.startswith("_") and name not in {"_exceptions", "annotations"}
    ]
