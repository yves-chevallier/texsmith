from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece


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
        description="Minted-based code listings used by Markdown code blocks.",
        source=template_path,
        context_defaults={"extra_packages": ""},
        should_render=_uses_code,
    )


def _uses_code(context: Mapping[str, object]) -> bool:
    """Detect whether code environments appear in rendered slot content."""
    for value in context.values():
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if "\\begin{code" in lowered or "\\begin{minted" in lowered:
            return True
    return False


__all__ = ["create_fragment"]
