"""Centralised resolution of the TeXSmith user and cache directories."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from threading import RLock


__all__ = [
    "TexsmithUserDir",
    "configure_user_dir",
    "get_user_dir",
    "set_user_dir",
    "user_dir_context",
]

_USER_DIR: TexsmithUserDir | None = None
_LOCK: RLock = RLock()


def _resolve_root(root: str | Path | None) -> tuple[Path, bool]:
    if root is not None:
        return Path(root).expanduser(), True
    env_root = os.environ.get("TEXSMITH_HOME")
    if env_root:
        return Path(env_root).expanduser(), True
    return Path.home() / ".texsmith", False


def _resolve_cache_root(
    cache_root: str | Path | None,
    *,
    user_root: Path,
    root_was_explicit: bool,
) -> tuple[Path, bool]:
    if cache_root is not None:
        return Path(cache_root).expanduser(), True
    env_cache = os.environ.get("TEXSMITH_CACHE_DIR")
    if env_cache:
        return Path(env_cache).expanduser(), True
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "texsmith", True
    if root_was_explicit:
        return user_root / "cache", True
    return Path.home() / ".cache" / "texsmith", False


@dataclass(slots=True)
class TexsmithUserDir:
    """Resolved user and cache roots plus helpers to manage them."""

    root: Path
    cache_root: Path
    root_is_explicit: bool = False
    cache_is_explicit: bool = False

    def data_dir(self, *parts: str | Path, create: bool = True) -> Path:
        """Return a directory under the user root, creating it when requested."""
        target = self.root.joinpath(*parts)
        if create:
            target.mkdir(parents=True, exist_ok=True)
        return target

    def cache_dir(self, *parts: str | Path, create: bool = True) -> Path:
        """Return a directory under the cache root, creating it when requested."""
        target = self.cache_root.joinpath(*parts)
        if create:
            target.mkdir(parents=True, exist_ok=True)
        return target

    def data_path(self, *parts: str | Path, create: bool = True) -> Path:
        """Return a path under the user root, creating parent directories if needed."""
        target = self.root.joinpath(*parts)
        if create:
            target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def cache_path(self, *parts: str | Path, create: bool = True) -> Path:
        """Return a path under the cache root, creating parent directories if needed."""
        target = self.cache_root.joinpath(*parts)
        if create:
            target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def clear_cache(self, namespaces: Iterable[str] | None = None) -> list[Path]:
        """Clear cached namespaces and return the list of removed paths."""
        targets: list[Path] = []
        if namespaces is None:
            targets.append(self.cache_root)
        else:
            for name in namespaces:
                targets.append(self.cache_root / name)
                targets.append(self.root / name)

        cleared: list[Path] = []
        for path in targets:
            if not path.exists():
                continue
            try:
                shutil.rmtree(path)
                cleared.append(path)
            except OSError:
                continue
        return cleared


def configure_user_dir(
    *,
    root: str | Path | None = None,
    cache_root: str | Path | None = None,
) -> TexsmithUserDir:
    """Replace the global user dir singleton with a freshly resolved instance."""
    user_root, root_was_explicit = _resolve_root(root)
    resolved_cache_root, cache_was_explicit = _resolve_cache_root(
        cache_root, user_root=user_root, root_was_explicit=root_was_explicit
    )
    return set_user_dir(
        TexsmithUserDir(
            root=user_root,
            cache_root=resolved_cache_root,
            root_is_explicit=root_was_explicit,
            cache_is_explicit=cache_was_explicit,
        )
    )


def get_user_dir() -> TexsmithUserDir:
    """Return the lazily created user dir singleton."""
    global _USER_DIR
    with _LOCK:
        if _USER_DIR is None:
            _USER_DIR = configure_user_dir()
            return _USER_DIR
        current_root, root_was_explicit = _resolve_root(None)
        current_cache_root, cache_was_explicit = _resolve_cache_root(
            None, user_root=current_root, root_was_explicit=root_was_explicit
        )
        if (not _USER_DIR.root_is_explicit and _USER_DIR.root != current_root) or (
            not _USER_DIR.cache_is_explicit and _USER_DIR.cache_root != current_cache_root
        ):
            _USER_DIR = TexsmithUserDir(
                root=current_root,
                cache_root=current_cache_root,
                root_is_explicit=root_was_explicit,
                cache_is_explicit=cache_was_explicit,
            )
        return _USER_DIR


def set_user_dir(user_dir: TexsmithUserDir) -> TexsmithUserDir:
    """Replace the current user dir singleton and return it."""
    global _USER_DIR
    with _LOCK:
        _USER_DIR = user_dir
        return _USER_DIR


@contextmanager
def user_dir_context(
    *,
    root: str | Path | None = None,
    cache_root: str | Path | None = None,
) -> Iterable[TexsmithUserDir]:
    """Temporarily override the global user dir singleton."""
    global _USER_DIR
    with _LOCK:
        previous = _USER_DIR
    current = configure_user_dir(root=root, cache_root=cache_root)
    try:
        yield current
    finally:
        with _LOCK:
            _USER_DIR = previous
