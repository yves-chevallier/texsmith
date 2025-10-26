"""TeXSmith command-line interface package."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["DEFAULT_MARKDOWN_EXTENSIONS", "app", "bibliography_app", "build", "convert", "main"]


def __getattr__(name: str) -> Any:
    if name == "DEFAULT_MARKDOWN_EXTENSIONS":
        from ..markdown import DEFAULT_MARKDOWN_EXTENSIONS as extensions

        globals()[name] = extensions
        return extensions
    if name in {"app", "bibliography_app", "main"}:
        module = import_module(".app", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {"build", "convert"}:
        module = import_module(".commands", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(__all__))
