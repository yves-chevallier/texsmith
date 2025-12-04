from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece


@dataclass(frozen=True)
class FontsConfig:
    """No-op config: fonts fragment only renders its package."""

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> FontsConfig:
        _ = context
        return cls()

    def inject_into(self, context: dict[str, Any]) -> None:
        _ = context


class FontsFragment(BaseFragment[FontsConfig]):
    name: ClassVar[str] = "ts-fonts"
    description: ClassVar[str] = "Font selection and fallbacks for TeXSmith templates."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-fonts.jinja.sty"),
            kind="package",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[FontsConfig]] = FontsConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-fonts.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> FontsConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: FontsConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: FontsConfig) -> bool:
        _ = config
        return True


fragment = FontsFragment()

__all__ = ["FontsConfig", "FontsFragment", "fragment"]
