"""Public API exposing TeXSmith's hashtag index extension."""

from __future__ import annotations

from .extensions.index import (
    IndexEntry,
    IndexRegistry,
    TexsmithIndexExtension,
    clear_registry,
    get_registry,
)
from .extensions.index.markdown import makeExtension


try:  # Optional dependency: only needed when running as a MkDocs plugin.
    from .extensions.index.mkdocs_plugin import IndexPlugin
except ModuleNotFoundError as exc:
    if exc.name != "mkdocs":
        raise
    mkdocs_exc = exc

    class IndexPlugin:  # type: ignore[no-redef]
        """Placeholder when MkDocs isn't installed."""

        def __init__(self, *_: object, **__: object) -> None:
            raise ModuleNotFoundError(
                "MkDocs is required for the IndexPlugin; install 'mkdocs' or "
                "'mkdocs-texsmith' to use this plugin."
            ) from mkdocs_exc


from .extensions.index.renderer import register as register_renderer


__all__ = [
    "IndexEntry",
    "IndexPlugin",
    "IndexRegistry",
    "TexsmithIndexExtension",
    "clear_registry",
    "get_registry",
    "makeExtension",
    "register_renderer",
]
