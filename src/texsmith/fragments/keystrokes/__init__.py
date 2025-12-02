from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import Fragment, FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Conditional keystroke helpers."""
    template_path = Path(__file__).with_name("ts-keystrokes.jinja.sty")
    fragment = Fragment(
        name="ts-keystrokes",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="package",
                slot="extra_packages",
            )
        ],
        description="Keyboard shortcut rendering helpers loaded only when needed.",
        source=template_path,
        context_defaults={"extra_packages": ""},
        should_render=_uses_keystrokes,
    )
    return fragment.to_definition()


def _uses_keystrokes(context: Mapping[str, object]) -> bool:
    """Detect keystroke macros in the rendered context."""
    tokens = ("\\keystroke{", "\\keystrokes{")
    for value in context.values():
        if not isinstance(value, str):
            continue
        if any(token in value for token in tokens):
            return True
    return False


__all__ = ["create_fragment"]
