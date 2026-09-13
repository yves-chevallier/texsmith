"""What a file's extension says it is.

Six independent suffix sets used to answer this, and they disagreed: a
`.mdown` file passed the CLI's "looks like a document" test and was then
rejected by the reader, and a `.ris` was a bibliography inside a snippet
fence but a document on the command line. The families are named once here.
"""

from __future__ import annotations

from pathlib import Path


__all__ = [
    "BIBLIOGRAPHY_SUFFIXES",
    "FRONT_MATTER_SUFFIXES",
    "MARKDOWN_SUFFIXES",
    "is_bibliography",
    "is_front_matter",
    "is_markdown",
]

#: The extensions a Markdown source carries. This is what the reader accepts,
#: so it is also what the CLI may call a document.
MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})

#: A standalone front-matter document: metadata without a body.
FRONT_MATTER_SUFFIXES = frozenset({".yaml", ".yml"})

#: The bibliography formats the collection can parse. RIS is **not** one of
#: them: nothing in ``core/bibliography`` reads it.
BIBLIOGRAPHY_SUFFIXES = frozenset({".bib", ".bibtex"})


def _suffix(path: Path | str) -> str:
    return Path(path).suffix.lower()


def is_markdown(path: Path | str) -> bool:
    """Whether ``path`` names a Markdown source."""
    return _suffix(path) in MARKDOWN_SUFFIXES


def is_front_matter(path: Path | str) -> bool:
    """Whether ``path`` names a standalone front-matter document."""
    return _suffix(path) in FRONT_MATTER_SUFFIXES


def is_bibliography(path: Path | str) -> bool:
    """Whether ``path`` names a bibliography the collection can load."""
    return _suffix(path) in BIBLIOGRAPHY_SUFFIXES
