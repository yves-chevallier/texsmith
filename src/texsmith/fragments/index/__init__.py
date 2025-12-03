from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece


@dataclass(frozen=True)
class IndexConfig:
    has_index: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> IndexConfig:
        has_flag = context.get("has_index")
        entries = context.get("index_terms")
        return cls(has_index=bool(has_flag) or bool(entries))

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_index_enabled"] = self.has_index


class IndexFragment(BaseFragment[IndexConfig]):
    name: ClassVar[str] = "ts-index"
    description: ClassVar[str] = "Index helpers with backmatter insertion."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-index.jinja.sty"),
            kind="package",
            slot="extra_packages",
        ),
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-index-backmatter.jinja.tex"),
            kind="inline",
            slot="fragment_backmatter",
        ),
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[IndexConfig]] = IndexConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-index.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": "", "fragment_backmatter": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> IndexConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: IndexConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: IndexConfig) -> bool:
        return config.has_index


fragment = IndexFragment()

__all__ = ["IndexConfig", "IndexFragment", "fragment"]
