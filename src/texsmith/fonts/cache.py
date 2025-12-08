"""Lightweight cache utilities for font-related assets."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import tempfile

from texsmith.core.user_dir import get_user_dir


DEFAULT_ROOT = get_user_dir().data_dir("fonts", create=False)


class FontCache:
    """Resolve persistent and temporary paths for font tooling.

    The cache defaults to ``~/.texsmith/fonts`` so that repeated runs of the
    toolchain can reuse downloaded assets (CTAN packages, lookup indexes, ...).
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_user_dir().data_dir("fonts", create=False)

    def ensure(self) -> Path:
        """Ensure the cache root exists and return it."""
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def path(self, *parts: str | Path) -> Path:
        """Return a path under the cache root, creating parent directories."""
        base = self.ensure()
        target = base.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    @contextmanager
    def tempdir(self) -> Iterator[Path]:
        """Provide a temporary directory inside the cache root."""
        self.ensure()
        with tempfile.TemporaryDirectory(dir=self.root) as tmp:
            yield Path(tmp)


__all__ = ["DEFAULT_ROOT", "FontCache"]
