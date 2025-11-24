from __future__ import annotations

from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Return the fonts fragment definition."""
    template_path = Path(__file__).with_name("ts-fonts.sty.jinja")
    return FragmentDefinition(
        name="ts-fonts",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="package",
                slot="extra_packages",
            )
        ],
        description="Font selection and fallbacks for TeXSmith templates.",
        source=template_path,
        context_defaults={"extra_packages": ""},
    )


__all__ = ["create_fragment"]
