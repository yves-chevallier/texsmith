from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec


def create_fragment() -> FragmentDefinition:
    """Return the code listings fragment definition."""
    template_path = Path(__file__).with_name("ts-code.jinja.sty")
    return FragmentDefinition(
        name="ts-code",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="package",
                slot="extra_packages",
            )
        ],
        description="Configurable code listings used by Markdown code blocks.",
        source=template_path,
        context_defaults={"extra_packages": ""},
        attributes={
            "code": TemplateAttributeSpec(
                default={"engine": "pygments", "style": "bw"},
                type="mapping",
                normaliser="code_options",
                sources=[
                    "press.code",
                    "code",
                ],
            )
        },
        should_render=_uses_code,
    )


def _uses_code(context: Mapping[str, object]) -> bool:
    """Detect whether code environments appear in rendered slot content."""
    for value in context.values():
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if "\\begin{code" in lowered or "\\begin{minted" in lowered or "\\py{" in lowered:
            return True
    return False


__all__ = ["create_fragment"]
