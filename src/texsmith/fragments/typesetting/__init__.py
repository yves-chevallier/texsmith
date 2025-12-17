from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec, TemplateError


@dataclass(frozen=True)
class TypesettingConfig:
    indent_mode: str | None
    parskip: str | None
    leading_mode: str | None
    leading_value: str | None
    lineno_enabled: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> TypesettingConfig:
        paragraph = context.get("typesetting_paragraph")
        leading = context.get("typesetting_leading")
        lineno = bool(context.get("typesetting_lineno"))

        indent_mode, parskip = _normalise_paragraph(paragraph)
        leading_mode, leading_value = _normalise_leading(leading)

        return cls(
            indent_mode=indent_mode,
            parskip=parskip,
            leading_mode=leading_mode,
            leading_value=leading_value,
            lineno_enabled=lineno,
        )

    def enabled(self) -> bool:
        return (
            any(
                option is not None for option in (self.indent_mode, self.parskip, self.leading_mode)
            )
            or self.lineno_enabled
        )

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_typesetting_indent_mode"] = self.indent_mode
        context["ts_typesetting_parskip"] = self.parskip
        context["ts_typesetting_leading_mode"] = self.leading_mode
        context["ts_typesetting_leading_value"] = self.leading_value
        context["ts_typesetting_enable_lineno"] = self.lineno_enabled
        context["ts_typesetting_enabled"] = self.enabled()


class TypesettingFragment(BaseFragment[TypesettingConfig]):
    name: ClassVar[str] = "ts-typesetting"
    description: ClassVar[str] = "Paragraph spacing, line spacing, and line numbers controls."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-typesetting.tex.jinja"),
            kind="inline",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]] = {
        "typesetting_paragraph": TemplateAttributeSpec(
            default=None,
            type="mapping",
            sources=[
                "typesetting.paragraph",
                "paragraph",
            ],
        ),
        "typesetting_leading": TemplateAttributeSpec(
            default=None,
            type="string",
            allow_empty=True,
            sources=[
                "typesetting.leading",
                "leading",
            ],
        ),
        "typesetting_lineno": TemplateAttributeSpec(
            default=None,
            type="boolean",
            sources=[
                "typesetting.lineno",
                "lineno",
            ],
        ),
    }

    config_cls: ClassVar[type[TypesettingConfig]] = TypesettingConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-typesetting.tex.jinja")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> TypesettingConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: TypesettingConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: TypesettingConfig) -> bool:
        return config.enabled()


def _normalise_paragraph(payload: Any) -> tuple[str | None, str | None]:
    indent_mode: str | None = None
    spacing: str | None = None

    if payload is None:
        return (indent_mode, spacing)

    if isinstance(payload, Mapping):
        indent_mode = _normalise_indent(payload.get("indent"))
        spacing = _normalise_spacing(payload.get("spacing"))
        return (indent_mode, spacing)

    indent_mode = _normalise_indent(payload)
    return (indent_mode, spacing)


def _normalise_indent(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return "always" if value else "none"

    if isinstance(value, (int, float)):
        return "always" if value else "none"

    if isinstance(value, str):
        token = value.strip().lower()
        if not token:
            return None
        if token == "auto":
            return "auto"
        if token in {"true", "yes", "on", "indent", "indented"}:
            return "always"
        if token in {"false", "no", "off", "none"}:
            return "none"
    raise TemplateError("paragraph.indent must be one of: true, false, auto.")


def _normalise_spacing(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        formatted = _format_number(float(value))
        return f"{formatted}pt"

    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None

    raise TemplateError("paragraph.spacing must be a string or number.")


def _normalise_leading(value: Any) -> tuple[str | None, str | None]:
    if value is None:
        return (None, None)

    if isinstance(value, (int, float)):
        factor = float(value)
        if factor <= 0:
            raise TemplateError("leading must be a positive value.")
        return ("factor", _format_number(factor))

    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return (None, None)

        token = trimmed.lower()
        if token in {"single", "singlespace", "singlespacing"}:
            return ("single", None)
        if token in {"onehalf", "one-half", "onehalfspacing", "one half"}:
            return ("onehalf", None)
        if token in {"double", "doublespacing", "double-spacing"}:
            return ("double", None)

        try:
            factor = float(trimmed)
        except ValueError:
            return ("length", trimmed)

        if factor <= 0:
            raise TemplateError("leading must be a positive value.")
        return ("factor", _format_number(factor))

    raise TemplateError(
        "leading must be 'single', 'onehalf', 'double', a length, or a positive number."
    )


def _format_number(value: float) -> str:
    rounded = f"{value:.3f}"
    cleaned = rounded.rstrip("0").rstrip(".")
    return cleaned or "0"


fragment = TypesettingFragment()

__all__ = ["TypesettingConfig", "TypesettingFragment", "fragment"]
