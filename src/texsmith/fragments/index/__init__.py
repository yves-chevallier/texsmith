from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.fragments.resolution import contract_active


@dataclass(frozen=True)
class IndexConfig:
    has_index: bool
    #: Named registries (``Requires.index``) → ``\makeindex[name=…]``.
    registries: tuple[str, ...] = ()

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> IndexConfig:
        has_flag = context.get("has_index")
        entries = context.get("index_terms")
        has_index = bool(has_flag) or bool(entries)
        active = contract_active(context, "ts-index")
        if active is not None:
            has_index = has_index or active
        raw = context.get("index_registries") or ()
        registries = tuple(
            dict.fromkeys(str(name) for name in raw if isinstance(name, str) and name.strip())
        )
        return cls(has_index=has_index, registries=registries)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_index_enabled"] = self.has_index
        context["ts_index_registries"] = list(self.registries)


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

    def should_render(self, config: IndexConfig) -> bool:
        return config.has_index


fragment = IndexFragment()

__all__ = ["IndexConfig", "IndexFragment", "fragment"]
