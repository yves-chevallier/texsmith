"""Utilities for post-processing generated LaTeX artefacts."""

from __future__ import annotations

import re


def squash_blank_lines(text: str) -> str:
    """Trim trailing whitespace and collapse runs of blank lines."""
    trimmed = re.sub(r"[ \t]+(?=\r?\n|$)", "", text)
    return re.sub(r"\n{3,}", "\n\n", trimmed)


__all__ = ["squash_blank_lines"]
