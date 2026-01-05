"""Package version helpers shared across interfaces."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version


def get_version() -> str:
    """Return the installed TeXSmith version (dynamic via hatch-vcs)."""
    try:
        return _pkg_version("texsmith")
    except PackageNotFoundError:
        return "0.0.0"


__all__ = ["get_version"]
