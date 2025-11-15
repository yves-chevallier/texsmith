"""Heuristics shared across handlers to detect Mermaid diagrams."""

from __future__ import annotations


MERMAID_KEYWORDS = {
    "graph",
    "flowchart",
    "sequencediagram",
    "classdiagram",
    "statediagram",
    "gantt",
    "erdiagram",
    "journey",
}


def looks_like_mermaid(diagram: str) -> bool:
    """Return True when the payload resembles a Mermaid diagram."""
    if not diagram:
        return False

    for line in diagram.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("%%"):
            continue
        token = stripped.split(maxsplit=1)[0].lower()
        return token in MERMAID_KEYWORDS

    return False


__all__ = ["looks_like_mermaid", "MERMAID_KEYWORDS"]
