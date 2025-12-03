from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece


@dataclass(frozen=True)
class BibliographyConfig:
    has_citations: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> BibliographyConfig:
        return cls(has_citations=bool(context.get("citations")))

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_bibliography_enabled"] = self.has_citations


class BibliographyFragment(BaseFragment[BibliographyConfig]):
    name: ClassVar[str] = "ts-bibliography"
    description: ClassVar[str] = (
        "Bibliography helpers (packages + backmatter) loaded when citations are present."
    )
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-bibliography.jinja.tex"),
            kind="inline",
            slot="extra_packages",
        ),
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-bibliography-backmatter.jinja.tex"),
            kind="inline",
            slot="fragment_backmatter",
        ),
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[BibliographyConfig]] = BibliographyConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-bibliography.jinja.tex")

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> BibliographyConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: BibliographyConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: BibliographyConfig) -> bool:
        return config.has_citations


fragment = BibliographyFragment()

__all__ = ["BibliographyConfig", "BibliographyFragment", "fragment"]
