from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece


@dataclass(frozen=True)
class TodolistConfig:
    uses_todolist: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> TodolistConfig:
        return cls(uses_todolist=_detect_todolist(context))

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
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[TodolistConfig]] = TodolistConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-todolist.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> TodolistConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: TodolistConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: TodolistConfig) -> bool:
        return config.uses_todolist


def _detect_todolist(context: Mapping[str, Any]) -> bool:
    tokens = ("\\done", "\\wontfix", "\\begin{todolist}", "\\todolist")
    for value in context.values():
        if not isinstance(value, str):
            continue
        if any(token in value for token in tokens):
            return True
    return False


fragment = TodolistFragment()

__all__ = ["TodolistConfig", "TodolistFragment", "fragment"]
