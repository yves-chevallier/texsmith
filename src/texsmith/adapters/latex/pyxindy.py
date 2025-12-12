"""Helpers to integrate the PyXindy toolchain (Python port of xindy)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil
import sys


def _python_module_available() -> bool:
    """Return True when the PyXindy modules are importable."""
    return importlib.util.find_spec("xindy") is not None


def is_available() -> bool:
    """Check whether PyXindy can be invoked (entry points or module)."""
    return _python_module_available() or shutil.which("makeindex-py") is not None


def _script_path(name: str) -> Path | None:
    """Resolve a script living alongside the current interpreter."""
    candidate = Path(sys.executable).with_name(name)
    return candidate if candidate.exists() else None


def index_command_tokens() -> list[str]:
    """Return the argv tokens to invoke the makeindex-compatible wrapper."""
    for candidate in ("makeindex-py", "makeindex4"):
        resolved = shutil.which(candidate) or _script_path(candidate)
        if resolved:
            return [str(resolved)]
    return [sys.executable, "-m", "xindy.tex.makeindex4"]


def glossary_command_tokens() -> list[str]:
    """Return the argv tokens to invoke the makeglossaries helper."""
    for candidate in ("makeglossaries-py",):
        resolved = shutil.which(candidate) or _script_path(candidate)
        if resolved:
            return [str(resolved)]
    return [sys.executable, "-m", "xindy.tex.makeglossaries"]


def latexmk_makeindex_command() -> str:
    """Return a makeindex command string suitable for latexmkrc."""
    tokens = [shlex.quote(token) for token in index_command_tokens()]
    return " ".join([*tokens, "%O", "-o", "%D", "%S"])


def latexmk_makeglossaries_command() -> str:
    """Return a makeglossaries command string suitable for latexmkrc."""
    tokens = [shlex.quote(token) for token in glossary_command_tokens()]
    return " ".join([*tokens, '"$base"'])


__all__ = [
    "glossary_command_tokens",
    "index_command_tokens",
    "is_available",
    "latexmk_makeglossaries_command",
    "latexmk_makeindex_command",
]
