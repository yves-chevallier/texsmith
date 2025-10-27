"""Conversion context primitives kept at the historical import path."""
# pyright: reportUnsupportedDunderAll=false

from __future__ import annotations

from texsmith.core import conversion_contexts as _conversion_contexts
from texsmith.core.conversion_contexts import *


__all__ = list(getattr(_conversion_contexts, "__all__", []))
if not __all__:
    __all__ = [
        name
        for name in globals()
        if not name.startswith("_") and name not in {"_conversion_contexts", "annotations"}
    ]
