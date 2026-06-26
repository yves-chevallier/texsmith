"""Backend-agnostic IR queries shared by the LaTeX and Typst writers.

Citation/footnote-identifier parsing and small tree lookups that both writers
need. Kept here so the two backends share a single implementation rather than
each carrying a verbatim copy.
"""

from __future__ import annotations

from collections.abc import Sequence
import re

from texsmith import ir


_DOI_KEY_PATTERN = r"10\.\d{4,9}/[^\s,\]]+"
_DOI_KEY_RE = re.compile(rf"^{_DOI_KEY_PATTERN}$")
_CITATION_KEY_PATTERN = rf"(?:{_DOI_KEY_PATTERN}|[A-Za-z0-9_\-:]+)"
_CITATION_PAYLOAD_RE = re.compile(
    rf"^\s*({_CITATION_KEY_PATTERN}(?:\s*,\s*{_CITATION_KEY_PATTERN})*)\s*$"
)


def _normalise_footnote_id(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if ":" in text:
        prefix, suffix = text.split(":", 1)
        if prefix.startswith("fnref") or prefix.startswith("fn"):
            return suffix
    return text


def _is_doi_key(candidate: str) -> bool:
    return bool(_DOI_KEY_RE.match(candidate.strip()))


def _split_citation_keys(identifier: str) -> list[str]:
    if not identifier:
        return []
    if "," not in identifier:
        return [identifier.strip()] if _is_doi_key(identifier) else []
    return [part.strip() for part in identifier.split(",") if part.strip()]


def _citation_keys_from_payload(text: str | None) -> list[str]:
    """Citation keys when a footnote body is just a key list (else empty)."""
    if not text:
        return []
    match = _CITATION_PAYLOAD_RE.match(text)
    if not match:
        return []
    return [key.strip() for key in match.group(1).split(",") if key.strip()]


def _find_image(blocks: Sequence[ir.Block]) -> ir.Image | None:
    from texsmith.ir.visitor import walk

    for block in blocks:
        for node in walk(block):
            if isinstance(node, ir.Image):
                return node
    return None


def _find_table(blocks: Sequence[ir.Block]) -> ir.Table | None:
    from texsmith.ir.visitor import walk

    for block in blocks:
        for node in walk(block):
            if isinstance(node, ir.Table):
                return node
    return None
