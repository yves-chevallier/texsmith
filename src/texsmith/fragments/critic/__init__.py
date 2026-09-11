"""``ts-critic`` fragment — critic markup (tmark M5).

Provides ``\\tsins``, ``\\tsdel``, ``\\tssubst`` and ``\\tscomment``
(fragment-contracts.md §1: the former ``add``/``addition``, ``del``/
``deletion``, ``substitution`` and ``comment`` partials). The fragment renders
when the writer names it in ``Requires.fragments``; on the legacy path it
renders when a contract macro appears in the rendered content.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.fragments.resolution import contract_active


@dataclass(frozen=True)
class CriticConfig:
    uses_critic: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> CriticConfig:
        active = contract_active(context, "ts-critic")
        return cls(uses_critic=_detect_critic(context) if active is None else active)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_critic_enabled"] = self.uses_critic


class CriticFragment(BaseFragment[CriticConfig]):
    name: ClassVar[str] = "ts-critic"
    description: ClassVar[str] = "Critic markup: insertions, deletions, substitutions, comments."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-critic.jinja.sty"),
            kind="package",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[CriticConfig]] = CriticConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-critic.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def should_render(self, config: CriticConfig) -> bool:
        return config.uses_critic


def _detect_critic(context: Mapping[str, Any]) -> bool:
    tokens = ("\\tsins{", "\\tsdel{", "\\tssubst{", "\\tscomment{")
    for value in context.values():
        if not isinstance(value, str):
            continue
        if any(token in value for token in tokens):
            return True
    return False


fragment = CriticFragment()

__all__ = ["CriticConfig", "CriticFragment", "fragment"]
