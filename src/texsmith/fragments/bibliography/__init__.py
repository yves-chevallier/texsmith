from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import Fragment, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Conditional bibliography rendering (packages + backmatter)."""
    template_path = Path(__file__).with_name("ts-bibliography.jinja.tex")
    backmatter_path = Path(__file__).with_name("ts-bibliography-backmatter.jinja.tex")
    fragment = Fragment(
        name="ts-bibliography",
        pieces=[
            FragmentPiece(template_path=template_path, kind="inline", slot="extra_packages"),
            FragmentPiece(template_path=backmatter_path, kind="inline", slot="fragment_backmatter"),
        ],
        description="Bibliography helpers (packages + backmatter) loaded when citations are present.",
        source=template_path,
        context_defaults={},
        should_render=_has_citations,
    )
    return fragment.to_definition()


def _has_citations(context: Mapping[str, object]) -> bool:
    citations = context.get("citations")
    return bool(citations)


__all__ = ["create_fragment"]
