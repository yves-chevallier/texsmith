from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece


@dataclass(frozen=True)
class GlossaryConfig:
    has_entries: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> GlossaryConfig:
        glossary = context.get("glossary")
        acronyms = context.get("acronyms")
        has_entries = bool(glossary) or bool(acronyms)
        return cls(has_entries=has_entries)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_glossary_enabled"] = self.has_entries


class GlossaryFragment(BaseFragment[GlossaryConfig]):
    name: ClassVar[str] = "ts-glossary"
    description: ClassVar[str] = "Glossary and acronym helpers."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-glossary.jinja.sty"),
            kind="package",
            slot="extra_packages",
        ),
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-glossary-backmatter.jinja.tex"),
            kind="inline",
            slot="fragment_backmatter",
        ),
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[GlossaryConfig]] = GlossaryConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-glossary.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": "", "fragment_backmatter": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> GlossaryConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: GlossaryConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: GlossaryConfig) -> bool:
        return config.has_entries


fragment = GlossaryFragment()

__all__ = ["GlossaryConfig", "GlossaryFragment", "fragment"]
