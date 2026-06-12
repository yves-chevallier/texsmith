"""MkDocs build hooks supporting documentation configuration.

These hooks only adjust build-time behaviour; they do not alter the source
documents. They provide a temporary `texsmith.plugins` namespace so
mkdocstrings can render the existing plugin reference while the packaging
story is fleshed out.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any


def on_config(config: Any) -> Any:
    """Inject a stub `texsmith.plugins` package for mkdocstrings lookups."""
    if (
        "texsmith.plugins" not in sys.modules
        and importlib.util.find_spec("texsmith.plugins") is None
    ):
        from texsmith.adapters.plugins import material

        module = types.ModuleType("texsmith.plugins")
        module.material = material
        module.__all__ = ["material"]
        module.__path__ = []  # make it importable as a namespace package
        module.__spec__ = importlib.util.spec_from_loader(
            "texsmith.plugins", loader=None, is_package=True
        )
        sys.modules["texsmith.plugins"] = module
        sys.modules["texsmith.plugins.material"] = material

    return config


def on_page_markdown(markdown: str, page: Any, config: Any = None, files: Any = None) -> str:  # noqa: ARG001
    """Apply small markdown fixes needed by the docs build."""
    if page.file.src_path == "markdown/references.md" and "[index]:" not in markdown:
        return markdown + "\n[index]: ../markdown/notes/#index\n"
    return markdown
