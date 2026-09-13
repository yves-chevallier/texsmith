from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.activation import required_fragment
from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.fragments.resolution import contract_active


@dataclass(frozen=True)
class TodolistConfig:
    uses_todolist: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> TodolistConfig:
        active = contract_active(context, "ts-todolist")
        return cls(uses_todolist=_detect_todolist(context) if active is None else active)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_todolist_enabled"] = self.uses_todolist


class TodolistFragment(BaseFragment[TodolistConfig]):
    name: ClassVar[str] = "ts-todolist"
    description: ClassVar[str] = (
        "Todolist helper commands loaded when checklist macros are present."
    )
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-todolist.jinja.sty"),
            kind="package",
            variable="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[TodolistConfig]] = TodolistConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-todolist.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def should_render(self, config: TodolistConfig) -> bool:
        return config.uses_todolist


def _detect_todolist(context: Mapping[str, Any]) -> bool:
    # IR path: the writer named the contract (fragment-contracts.md §2).
    if required_fragment(context, "ts-todolist"):
        return True
    tokens = ("\\done", "\\wontfix", "\\begin{todolist}", "\\todolist")
    for value in context.values():
        if not isinstance(value, str):
            continue
        if any(token in value for token in tokens):
            return True
    return False


fragment = TodolistFragment()

__all__ = ["TodolistConfig", "TodolistFragment", "fragment"]
