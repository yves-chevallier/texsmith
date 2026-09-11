"""Public entry points for TeXSmith's custom-counter extension."""

from __future__ import annotations

from .markdown import COUNTER_PATTERN, CountersExtension, makeExtension


__all__ = [
    "COUNTER_PATTERN",
    "CountersExtension",
    "makeExtension",
]
