from __future__ import annotations

from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Return the index helpers fragment definition."""
    package_path = Path(__file__).with_name("ts-index.sty.jinja")
    backmatter_path = Path(__file__).with_name("ts-index-backmatter.jinja.tex")
    return FragmentDefinition(
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
    )


__all__ = ["create_fragment"]
