"""Public entry points for TeXSmith's hashtag index extension."""

from __future__ import annotations

from .markdown import TexsmithIndexExtension, makeExtension
from .registry import (
    IndexEntry,
    IndexRegistry,
    clear_registry,
    get_registry,
)


try:  # Optional dependency: only needed when running as a MkDocs plugin.
    from .mkdocs_plugin import IndexPlugin
except ModuleNotFoundError as exc:
    if exc.name != "mkdocs":
        raise
    _mkdocs_exc = exc

    class IndexPlugin:  # type: ignore[no-redef]
        """Placeholder raised when MkDocs isn't installed."""

        def __init__(self, *_: object, **__: object) -> None:
            raise ModuleNotFoundError(
                "MkDocs is required for the IndexPlugin; install 'mkdocs' or "
                "'mkdocs-texsmith' to use this plugin."
            ) from _mkdocs_exc


__all__ = [
    "IndexEntry",
    "IndexPlugin",
    "IndexRegistry",
    "TexsmithIndexExtension",
    "clear_registry",
    "get_registry",
    "makeExtension",
]
