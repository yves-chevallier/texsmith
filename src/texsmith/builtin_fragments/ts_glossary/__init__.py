from __future__ import annotations

from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Return the glossary/acronyms fragment definition."""
    package_path = Path(__file__).with_name("ts-glossary.sty.jinja")
    backmatter_path = Path(__file__).with_name("ts-glossary-backmatter.jinja.tex")
    return FragmentDefinition(
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
    )


__all__ = ["create_fragment"]
