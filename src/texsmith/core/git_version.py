"""Resolve document ``version`` strings, including the magic ``git`` value.

The article (and other) templates accept a ``version`` front-matter field that
may be either a free-form label (``"Draft 3"``) or the literal sentinel
``"git"``. When ``git`` is requested, the resolved value comes from
``git describe --tags --dirty`` against the repository that contains the
document being compiled, falling back to a short commit hash if no tag exists.
A warning is emitted if git metadata cannot be read so users get an obvious
signal instead of silently empty output.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any
import warnings


_GIT_VERSION_CACHE: dict[Path, str] = {}


def reset_cache() -> None:
    """Clear the per-repository cache (used by tests)."""
    _GIT_VERSION_CACHE.clear()


def format_version(value: Any, *, cwd: Path | None = None) -> str:
    """Return the rendered version string for a front-matter ``version`` value.

    A free-form string is returned trimmed. The literal ``"git"`` (case-insensitive)
    is replaced with the output of :func:`git_describe`.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.lower() != "git":
        return text
    return git_describe(cwd=cwd)


def git_describe(*, cwd: Path | None = None) -> str:
    """Return ``git describe --tags --dirty`` (or a short hash) for ``cwd``.

    Returns an empty string and emits a warning when no git repository is
    found or git fails to execute. Results are cached per resolved repository
    root, so repeated lookups during a single build are cheap.
    """
    repo_root = resolve_git_root(cwd=cwd)
    if repo_root is None:
        warnings.warn(
            "version=git requested but no git repository was found; "
            "cannot resolve git version.",
            stacklevel=2,
        )
        return ""

    cached = _GIT_VERSION_CACHE.get(repo_root)
    if cached is not None:
        return cached

    describe = _run_git(repo_root, ["describe", "--tags", "--dirty"])
    if not describe:
        describe = _run_git(repo_root, ["rev-parse", "--short=7", "HEAD"])
        if describe:
            dirty = _run_git(repo_root, ["status", "--porcelain"])
            if dirty:
                describe = f"{describe}-dirty"

    if not describe:
        warnings.warn(
            "version=git requested but git metadata could not be read.",
            stacklevel=2,
        )

    _GIT_VERSION_CACHE[repo_root] = describe
    return describe


def resolve_git_root(*, cwd: Path | None = None) -> Path | None:
    """Locate the git toplevel containing ``cwd`` (defaults to the current dir)."""
    anchor = (cwd or Path.cwd()).resolve()
    if not anchor.exists():
        return None
    repo = _run_git(anchor, ["rev-parse", "--show-toplevel"])
    if not repo:
        return None
    return Path(repo)


def _run_git(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


__all__ = [
    "format_version",
    "git_describe",
    "reset_cache",
    "resolve_git_root",
]
