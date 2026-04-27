"""Low-level git helpers used by document metadata resolvers.

This module exposes the primitives — ``git_describe``, ``git_commit_date``,
``resolve_git_root`` — that ``texsmith.core.document_version`` and
``texsmith.core.document_date`` consume to render the front-matter ``version``
and ``date`` fields. The helpers warn (rather than raise) when git metadata is
unreachable so a missing repository surfaces in the build log without aborting
the document.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import subprocess
from typing import Any
import warnings


try:
    from datetime import UTC
except ImportError:  # pragma: no cover - py310 compatibility
    UTC = timezone.utc


_GIT_DESCRIBE_CACHE: dict[Path, str] = {}
_GIT_COMMIT_DATE_CACHE: dict[Path, date | None] = {}


def reset_cache() -> None:
    """Clear the per-repository caches (used by tests)."""
    _GIT_DESCRIBE_CACHE.clear()
    _GIT_COMMIT_DATE_CACHE.clear()


def git_describe(*, cwd: Path | None = None) -> str:
    """Return ``git describe --tags --dirty`` (or a short hash) for ``cwd``.

    Returns an empty string and emits a warning when no git repository is
    found or git fails to execute. Results are cached per resolved repository
    root, so repeated lookups during a single build are cheap.
    """
    repo_root = resolve_git_root(cwd=cwd)
    if repo_root is None:
        warnings.warn(
            "version=git requested but no git repository was found; cannot resolve git version.",
            stacklevel=2,
        )
        return ""

    cached = _GIT_DESCRIBE_CACHE.get(repo_root)
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

    _GIT_DESCRIBE_CACHE[repo_root] = describe
    return describe


def git_commit_date(*, cwd: Path | None = None) -> date | None:
    """Return the committer date of ``HEAD`` for the repository containing ``cwd``.

    Uses ``git log -1 --format=%cs`` (committer date in short ISO ``YYYY-MM-DD``
    form). Returns ``None`` and warns if the repository is missing or git fails.
    Cached per repository root.
    """
    repo_root = resolve_git_root(cwd=cwd)
    if repo_root is None:
        warnings.warn(
            "date=commit requested but no git repository was found; cannot resolve commit date.",
            stacklevel=2,
        )
        return None

    if repo_root in _GIT_COMMIT_DATE_CACHE:
        return _GIT_COMMIT_DATE_CACHE[repo_root]

    raw = _run_git(repo_root, ["log", "-1", "--format=%cs"])
    parsed: date | None
    if not raw:
        warnings.warn(
            "date=commit requested but no commit metadata could be read.",
            stacklevel=2,
        )
        parsed = None
    else:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC).date()
        except ValueError:
            warnings.warn(
                f"date=commit returned unparseable git output {raw!r}; ignoring.",
                stacklevel=2,
            )
            parsed = None

    _GIT_COMMIT_DATE_CACHE[repo_root] = parsed
    return parsed


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


def format_version(value: Any, *, cwd: Path | None = None) -> str:
    """Deprecated shim that forwards to :func:`texsmith.core.document_version.format_version`.

    Kept to preserve the public surface of older releases; new code should
    import from ``texsmith.core.document_version`` directly.
    """
    from texsmith.core.document_version import format_version as _format

    return _format(value, cwd=cwd)


__all__ = [
    "format_version",
    "git_commit_date",
    "git_describe",
    "reset_cache",
    "resolve_git_root",
]
