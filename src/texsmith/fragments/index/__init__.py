from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import Fragment, FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Return the index helpers fragment definition."""
    package_path = Path(__file__).with_name("ts-index.jinja.sty")
    backmatter_path = Path(__file__).with_name("ts-index-backmatter.jinja.tex")
    fragment = Fragment(
        name="ts-index",
        pieces=[
            FragmentPiece(
                template_path=package_path,
                kind="package",
                slot="extra_packages",
            ),
            FragmentPiece(
                template_path=backmatter_path,
                kind="inline",
                slot="fragment_backmatter",
            ),
        ],
        description="Index helpers with backmatter insertion.",
        source=package_path,
        context_defaults={"extra_packages": "", "fragment_backmatter": ""},
        should_render=_has_index,
    )
    return fragment.to_definition()


def _has_index(context: Mapping[str, object]) -> bool:
    """Render the index fragment only when index entries are present."""
    has_flag = context.get("has_index")
    if isinstance(has_flag, bool) and has_flag:
        return True
    entries = context.get("index_terms")
    return bool(entries)


__all__ = ["create_fragment"]
