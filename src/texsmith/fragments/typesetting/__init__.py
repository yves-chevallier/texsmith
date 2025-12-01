from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from texsmith.core.fragments import FragmentDefinition, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec, TemplateError


def create_fragment() -> FragmentDefinition:
    """Return the typesetting fragment definition."""
    template_path = Path(__file__).with_name("ts-typesetting.tex.jinja")
    return FragmentDefinition(
        name="ts-typesetting",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="inline",
                slot="extra_packages",
            )
        ],
        description="Paragraph spacing, line spacing, and line numbers controls.",
        source=template_path,
        context_defaults={"extra_packages": ""},
        context_injector=_inject_context,
        should_render=_should_render,
        attributes={
            "typesetting_paragraph": TemplateAttributeSpec(
                default=None,
                type="mapping",
                sources=[
                    "press.typesetting.paragraph",
                    "press.paragraph",
                    "typesetting.paragraph",
                    "paragraph",
                ],
            ),
            "typesetting_leading": TemplateAttributeSpec(
                default=None,
                type="string",
                allow_empty=True,
                sources=[
                    "press.typesetting.leading",
                    "press.leading",
                    "typesetting.leading",
                    "leading",
                ],
            ),
            "typesetting_lineno": TemplateAttributeSpec(
                default=None,
                type="boolean",
                sources=[
                    "press.typesetting.lineno",
                    "press.lineno",
                    "typesetting.lineno",
                    "lineno",
                ],
            ),
        },
    )


def _inject_context(
    context: dict[str, Any], overrides: Mapping[str, Any] | None = None
) -> None:
    _ = overrides
    paragraph = context.get("typesetting_paragraph")
    leading = context.get("typesetting_leading")
    lineno = context.get("typesetting_lineno")

    indent_mode, parskip = _normalise_paragraph(paragraph)
    leading_mode, leading_value = _normalise_leading(leading)
    lineno_enabled = bool(lineno)
    enabled = (
        any(option is not None for option in (indent_mode, parskip, leading_mode))
        or lineno_enabled
    )

    context["ts_typesetting_indent_mode"] = indent_mode
    context["ts_typesetting_parskip"] = parskip
    context["ts_typesetting_leading_mode"] = leading_mode
    context["ts_typesetting_leading_value"] = leading_value
    context["ts_typesetting_enable_lineno"] = lineno_enabled
    context["ts_typesetting_enabled"] = enabled


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


def _should_render(context: Mapping[str, object]) -> bool:
    return bool(context.get("ts_typesetting_enabled"))


__all__ = ["create_fragment"]
