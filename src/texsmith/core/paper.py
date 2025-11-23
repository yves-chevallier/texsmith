"""Helpers for normalising page geometry settings from front matter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from texsmith.core.templates.manifest import TemplateError


DEFAULT_MARGIN = "2.5cm"
_FORMAT_SUFFIX = "paper"
_KNOWN_FORMATS = {f"{family}{index}" for family in ("a", "b", "c") for index in range(0, 7)} | {
    "letter",
    "legal",
    "executive",
}


def _normalise_dimension(value: Any) -> str:
    """Return a LaTeX dimension string, converting bare numbers to millimetres."""
    if isinstance(value, (int, float)):
        return f"{value}mm"
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        try:
            float(stripped)
        except ValueError:
            return stripped
        return f"{stripped}mm"
    return str(value)


def _normalise_margin(value: Any) -> str | dict[str, str] | None:
    """Return a margin specification string or per-side mapping."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return f"{value}mm"
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered == "narrow":
            return "1.5cm"
        if lowered == "wide":
            return "3.0cm"
        try:
            float(cleaned)
        except ValueError:
            return cleaned
        return f"{cleaned}mm"
    if isinstance(value, dict):
        formatted: dict[str, str] = {}
        for key, raw in value.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            dim = _normalise_dimension(raw)
            if dim:
                formatted[key_str] = dim
        return formatted or None
    return None


class PaperSpec(BaseModel):
    """Validated paper settings parsed from front matter."""

    format: str | None = None
    width: str | None = None
    height: str | None = None
    orientation: Literal["portrait", "landscape"] = "portrait"
    margin: str | dict[str, str] | None = None
    frame: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _coerce_payload(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"format": data}
        if not isinstance(data, dict):
            return {}
        payload = dict(data)
        if "paper" in payload and "format" not in payload:
            payload["format"] = payload.pop("paper")
        return payload

    @field_validator("format")
    @classmethod
    def _normalise_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.strip().lower()
        if not lowered:
            return None
        if lowered.endswith(_FORMAT_SUFFIX):
            lowered = lowered[: -len(_FORMAT_SUFFIX)]
        if lowered and lowered not in _KNOWN_FORMATS:
            raise TemplateError(
                f"Unsupported paper format '{value}'. Expected one of: "
                f"{', '.join(sorted(_KNOWN_FORMATS))}."
            )
        return lowered

    @field_validator("width", "height")
    @classmethod
    def _format_dimensions(cls, value: Any) -> str | None:
        if value is None:
            return None
        dim = _normalise_dimension(value)
        return dim or None

    @field_validator("margin", mode="before")
    @classmethod
    def _format_margin(cls, value: Any) -> Any:
        return _normalise_margin(value)

    def to_documentclass_options(self) -> tuple[str | None, str | None]:
        paper_option = f"{self.format}{_FORMAT_SUFFIX}" if self.format else None
        orientation_option = "landscape" if self.orientation == "landscape" else None
        return paper_option, orientation_option

    def geometry_options(self, *, default_margin: str = DEFAULT_MARGIN) -> list[str]:
        options: list[str] = []
        margin_value = self.margin or default_margin
        if isinstance(margin_value, str):
            if margin_value:
                options.append(f"margin={margin_value}")
        elif isinstance(margin_value, dict):
            for key, dim in margin_value.items():
                if dim:
                    options.append(f"{key}={dim}")

        paper_option, orientation_option = self.to_documentclass_options()
        if paper_option:
            options.append(paper_option)
        if orientation_option:
            options.append(orientation_option)
        if self.width:
            options.append(f"paperwidth={self.width}")
        if self.height:
            options.append(f"paperheight={self.height}")

        if self.frame:
            options.append("showframe")

        for key, value in self.extra.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            if isinstance(value, bool):
                if value:
                    options.append(key_str)
                continue
            val_str = _normalise_dimension(value)
            if val_str:
                options.append(f"{key_str}={val_str}")

        return options

    def extra_options(self) -> list[str]:
        """Return only explicitly provided extra geometry options."""
        options: list[str] = []
        for key, value in self.extra.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            if isinstance(value, bool):
                if value:
                    options.append(key_str)
                continue
            val_str = _normalise_dimension(value)
            if val_str:
                options.append(f"{key_str}={val_str}")
        return options


@dataclass(slots=True)
class GeometryResolution:
    """Resolved geometry options injected into templates and fragments."""

    documentclass_options: str
    paper_option: str | None
    orientation_option: str | None
    geometry_options: str
    geometry_extra_options: str


def resolve_geometry_settings(
    context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
) -> GeometryResolution:
    """Resolve geometry settings from template context and overrides."""
    press_section = overrides.get("press") if isinstance(overrides, Mapping) else {}
    paper_raw = press_section.get("paper") if isinstance(press_section, Mapping) else None
    geometry_extra = press_section.get("geometry") if isinstance(press_section, Mapping) else None
    margin_raw = press_section.get("margin") if isinstance(press_section, Mapping) else None

    if paper_raw is None:
        paper_raw = context.get("paper")
    if geometry_extra is None:
        geometry_extra = context.get("geometry")
    if margin_raw is None:
        margin_raw = context.get("margin")

    payload: dict[str, Any] = {}
    if isinstance(paper_raw, Mapping):
        payload.update(paper_raw)
    elif paper_raw is not None:
        payload["format"] = paper_raw

    if "margin" not in payload and margin_raw is not None:
        payload["margin"] = margin_raw
    if "orientation" not in payload and context.get("orientation"):
        payload["orientation"] = context.get("orientation")

    if isinstance(geometry_extra, Mapping):
        formatted_extra: dict[str, str] = {}
        for key, raw in geometry_extra.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            if isinstance(raw, bool):
                if raw:
                    formatted_extra[key_str] = True  # type: ignore[assignment]
                continue
            val = _normalise_dimension(raw)
            if val:
                formatted_extra[key_str] = val
        if formatted_extra:
            payload["extra"] = formatted_extra

    spec = PaperSpec.model_validate(payload)
    geometry_options = ",".join(spec.geometry_options())
    geometry_extra_options = ",".join(spec.extra_options())
    paper_option, orientation_option = spec.to_documentclass_options()
    options = [opt for opt in (paper_option, orientation_option) if opt]
    documentclass_options = f"[{','.join(options)}]" if options else ""

    return GeometryResolution(
        documentclass_options=documentclass_options,
        paper_option=paper_option,
        orientation_option=orientation_option,
        geometry_options=geometry_options,
        geometry_extra_options=geometry_extra_options,
    )


__all__ = ["GeometryResolution", "resolve_geometry_settings"]
