"""Public entry points for TeXSmith's custom-counter extension."""

from __future__ import annotations

from .markdown import COUNTER_PATTERN, CountersExtension, makeExtension


try:  # Optional dependency: only needed when running as a MkDocs plugin.
    from .mkdocs_plugin import CountersPlugin
except ModuleNotFoundError as exc:
    if exc.name != "mkdocs":
        raise
    _mkdocs_exc = exc

    class CountersPlugin:  # type: ignore[no-redef]
        """Placeholder raised when MkDocs isn't installed."""

        def __init__(self, *_: object, **__: object) -> None:
            raise ModuleNotFoundError(
                "MkDocs is required for the CountersPlugin; install 'mkdocs' or "
                "'mkdocs-texsmith' to use this plugin."
            ) from _mkdocs_exc


__all__ = [
    "COUNTER_PATTERN",
    "CountersExtension",
    "CountersPlugin",
    "makeExtension",
]
