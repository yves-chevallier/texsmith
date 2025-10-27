"""Template utilities available at the legacy package path."""

from __future__ import annotations

from texsmith.core import templates as _templates
from texsmith.core.templates import *  # noqa: F401,F403

__all__ = list(getattr(_templates, "__all__", []))
if not __all__:
    __all__ = [
        name
        for name in globals()
        if not name.startswith("_") and name not in {"_templates", "annotations"}
    ]
