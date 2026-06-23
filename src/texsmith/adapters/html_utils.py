"""Generic BeautifulSoup attribute and asset-path helpers.

Pure utilities shared by the writer, the Markdown extensions and the
plugins. They contain no LaTeX and never mutate the soup.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse


def coerce_attribute(value: Any) -> str | None:
    """Normalise a BeautifulSoup attribute value to a string when possible."""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(value, Iterable):
        for item in value:
            if isinstance(item, str):
                return item
    return None


def gather_classes(value: Any) -> list[str]:
    """Return a list of classes extracted from a BeautifulSoup attribute."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return [cast(str, item) for item in value if isinstance(item, str)]
    return []


def resolve_asset_path(file_path: Path, path: str | Path) -> Path | None:
    """Resolve an asset path relative to a Markdown source file."""
    origin = Path(file_path)
    if origin.name == "index.md":
        origin = origin.parent
    target = (origin / path).resolve()
    return target if target.exists() else None


def is_valid_url(url: str) -> bool:
    """Check whether a URL string has a valid scheme/netloc combination."""
    try:
        result = urlparse(url)
    except ValueError:
        return False
    return bool(result.scheme and result.netloc)
