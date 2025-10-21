"""Utility helpers shared by the LaTeX renderer."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


try:  # pragma: no cover - graceful degradation
    import unidecode  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - optional dependency
    unidecode = None  # type: ignore[assignment]


def escape_latex_chars(text: str) -> str:
    """Escape LaTeX special characters in a string."""

    mapping = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("$", r"\$"),
        ("_", r"\_"),
        ("^", r"\^"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("\\", r"\textbackslash{}"),
    ]
    replacements = dict(mapping)
    return "".join(replacements.get(char, char) for char in text)


def to_kebab_case(name: str) -> str:
    """Convert a string to kebab case."""

    if unidecode is not None:
        name = unidecode.unidecode(name)  # type: ignore[attr-defined]
    else:
        normalized = unicodedata.normalize("NFKD", name)
        name = normalized.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s']", "", name)
    name = re.sub(r"[\s']+", "-", name)
    return name.lower()


def points_to_mm(points: float) -> float:
    """Convert points to millimetres."""

    return points * 25.4 / 72


def resolve_asset_path(file_path: Path, path: str | Path) -> Path | None:
    """Resolve an asset path relative to a Markdown source file."""

    file_path = Path(file_path)
    if file_path.name == "index.md":
        file_path = file_path.parent
    target = (file_path / path).resolve()
    return target if target.exists() else None


def is_valid_url(url: str) -> bool:
    """Check whether a URL is valid."""

    try:
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except ValueError:
        return False
