from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import Fragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec


def create_fragment() -> FragmentDefinition:
    """Return the callouts fragment definition."""
    template_path = Path(__file__).with_name("ts-callouts.jinja.sty")
    fragment = Fragment(
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
        attributes={
            "callout_style": TemplateAttributeSpec(
                default="fancy",
                type="string",
                choices=["fancy", "classic", "minimal"],
                sources=[
                    "press.callouts.style",
                    "callouts.style",
                    "callout_style",
                    "press.callout_style",
                ],
                normaliser="callout_style",
            )
        },
        should_render=_uses_callouts,
    )
    return fragment.to_definition()


def _uses_callouts(context: Mapping[str, object]) -> bool:
    """Detect whether callout environments are present in rendered slots."""
    for value in context.values():
        if not isinstance(value, str):
            continue
        if "\\begin{callout" in value:
            return True
    return False


__all__ = ["create_fragment"]
