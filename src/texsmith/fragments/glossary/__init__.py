from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import Fragment, FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Return the glossary/acronyms fragment definition."""
    package_path = Path(__file__).with_name("ts-glossary.jinja.sty")
    backmatter_path = Path(__file__).with_name("ts-glossary-backmatter.jinja.tex")
    fragment = Fragment(
        name="ts-glossary",
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
        description="Glossary and acronym helpers.",
        source=package_path,
        context_defaults={"extra_packages": "", "fragment_backmatter": ""},
        should_render=_has_glossary,
    )
    return fragment.to_definition()


def _has_glossary(context: Mapping[str, object]) -> bool:
    """Render glossary fragment only when glossary or acronyms exist."""
    if context.get("glossary"):
        return True
    acronyms = context.get("acronyms")
    return bool(acronyms)


__all__ = ["create_fragment"]
