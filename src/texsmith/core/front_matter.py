"""Split a document's YAML front matter from its body.

The parser owns front matter on the conversion path — ``tmark.parse`` types the
keys it knows and keeps the rest in ``extra``. This helper exists for the
callers that need the metadata *before* (or without) parsing: the CLI picks the
template declared in ``press.template`` to decide the output mode, the
conversion service merges the shared ``--front-matter`` files, and the snippet
compiler reads the header of a nested source. Front matter is a text convention,
not a Markdown feature, so the splitter is pure YAML with no parser behind it.
"""

from __future__ import annotations

from typing import Any

import yaml


__all__ = ["split_front_matter"]


def split_front_matter(source: str) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from Markdown content, returning metadata and body."""
    candidate = source.lstrip("﻿")
    prefix_len = len(source) - len(candidate)
    lines = candidate.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, source

    front_matter_lines: list[str] = []
    closing_index: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped in {"---", "..."}:
            closing_index = idx
            break
        front_matter_lines.append(line)

    if closing_index is None:
        return {}, source

    raw_block = "\n".join(front_matter_lines)
    try:
        metadata = yaml.safe_load(raw_block) or {}
    except yaml.YAMLError:
        return {}, source

    if not isinstance(metadata, dict):
        metadata = {}

    body_lines = lines[closing_index + 1 :]
    body = "\n".join(body_lines)
    if source.endswith("\n"):
        body += "\n"

    prefix = source[:prefix_len]
    return metadata, prefix + body
