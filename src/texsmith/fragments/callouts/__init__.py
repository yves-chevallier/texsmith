from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec


@dataclass(frozen=True)
class CalloutsConfig:
    style: str | None
    uses_callouts: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> CalloutsConfig:
        return cls(
            style=context.get("callout_style"),
            uses_callouts=_detect_callouts(context),
        )

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_callouts_style"] = self.style


class CalloutsFragment(BaseFragment[CalloutsConfig]):
    name: ClassVar[str] = "ts-callouts"
    description: ClassVar[str] = "Reusable callout styles shared by built-in templates."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-callouts.jinja.sty"),
            kind="package",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]] = {
        "callout_style": TemplateAttributeSpec(
            default="fancy",
            type="string",
            choices=["fancy", "classic", "minimal"],
            sources=[
                "callouts.style",
                "callout_style",
            ],
            normaliser="callout_style",
        )
    }
    config_cls: ClassVar[type[CalloutsConfig]] = CalloutsConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-callouts.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> CalloutsConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: CalloutsConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: CalloutsConfig) -> bool:
        return config.uses_callouts


def _detect_callouts(context: Mapping[str, Any]) -> bool:
    uses_flag = context.get("ts_uses_callouts")
    if isinstance(uses_flag, bool) and uses_flag:
        return True

    for value in context.values():
        if not isinstance(value, str):
            continue
        if "\\begin{callout" in value:
            return True
    return False


fragment = CalloutsFragment()

__all__ = ["CalloutsConfig", "CalloutsFragment", "fragment"]
