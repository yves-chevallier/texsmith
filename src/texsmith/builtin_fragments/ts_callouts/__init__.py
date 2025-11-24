from __future__ import annotations

from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Return the callouts fragment definition."""
    template_path = Path(__file__).with_name("ts-callouts.sty.jinja")
    return FragmentDefinition(
        name="ts-callouts",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="package",
                slot="extra_packages",
            )
        ],
        description="Reusable callout styles shared by built-in templates.",
        source=template_path,
        context_defaults={"extra_packages": ""},
    )


__all__ = ["create_fragment"]
