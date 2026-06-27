"""``ts-fonts`` fragment — font selection driven by ``fonts.family``.

The font-acquisition and fallback-context machinery lives in
:mod:`texsmith.fonts.provisioning`; this module is the thin fragment glue.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
import warnings

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec
from texsmith.fonts.provisioning import (
    _FAMILY_CHOICES,
    _ensure_ctan_sty,
    _normalise_family,
    _prepare_fallback_context,
    _prepare_mono_font,
    _resolve_output_dir,
)


@dataclass(frozen=True)
class FontsConfig:
    family: str
    output_dir: Path
    fallback: dict[str, Any] = field(default_factory=dict)
    mono_font: dict[str, Any] | None = None

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> FontsConfig:
        fonts_section = context.get("fonts")
        if isinstance(fonts_section, Mapping):
            raw_family = fonts_section.get("family")
        else:
            raw_family = context.get("fonts_family")
        family = _normalise_family(raw_family)
        output_dir = _resolve_output_dir(context)
        fallback = _prepare_fallback_context(context, output_dir=output_dir)
        mono_font = _prepare_mono_font(context, output_dir=output_dir, family=family)
        return cls(family=family, output_dir=output_dir, fallback=fallback, mono_font=mono_font)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["fonts_family"] = self.family
        fonts_section = context.get("fonts")
        merged = dict(fonts_section) if isinstance(fonts_section, Mapping) else {}
        merged["family"] = self.family
        if self.fallback and self.fallback.get("entries"):
            merged["fallback"] = self.fallback
        if self.mono_font:
            merged["mono_font"] = self.mono_font
        context["fonts"] = merged

        try:
            _ensure_ctan_sty(self.family, self.output_dir)
        except Exception as exc:  # pragma: no cover - network/path edge cases
            warnings.warn(
                f"Unable to prepare CTAN package for font '{self.family}': {exc}",
                stacklevel=2,
            )


class FontsFragment(BaseFragment[FontsConfig]):
    name: ClassVar[str] = "ts-fonts"
    description: ClassVar[str] = "Font selection driven by fonts.family."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-fonts.jinja.sty"),
            kind="package",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]] = {
        "fonts_family": TemplateAttributeSpec(
            default="lm",
            type="string",
            allow_empty=False,
            choices=sorted(set(_FAMILY_CHOICES.keys())),
            sources=[
                "fonts.family",
                "fonts_family",
                "font_family",
            ],
        )
    }
    config_cls: ClassVar[type[FontsConfig]] = FontsConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-fonts.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def should_render(self, config: FontsConfig) -> bool:
        _ = config
        return True


fragment = FontsFragment()

__all__ = ["FontsConfig", "FontsFragment", "fragment"]
