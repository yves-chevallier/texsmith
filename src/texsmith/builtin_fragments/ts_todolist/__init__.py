from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Conditional todolist helpers."""
    template_path = Path(__file__).with_name("ts-todolist.jinja.sty")
    return FragmentDefinition(
        name="ts-todolist",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="package",
                slot="extra_packages",
            )
        ],
        description="Todolist helper commands loaded when checklist macros are present.",
        source=template_path,
        context_defaults={"extra_packages": ""},
        should_render=_uses_todolist,
    )


def _uses_todolist(context: Mapping[str, object]) -> bool:
    tokens = ("\\done", "\\wontfix", "\\begin{todolist}", "\\todolist")
    for value in context.values():
        if not isinstance(value, str):
            continue
        if any(token in value for token in tokens):
            return True
    return False


__all__ = ["create_fragment"]
