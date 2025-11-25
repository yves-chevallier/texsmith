"""Geometry helpers scoped to the ts-geometry fragment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pint import DimensionalityError, UndefinedUnitError, UnitRegistry
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from texsmith.core.templates.manifest import TemplateError


DEFAULT_MARGIN: str | None = None
_FORMAT_SUFFIX = "paper"
_KNOWN_FORMATS = {f"{family}{index}" for family in ("a", "b", "c") for index in range(0, 7)} | {
    "letter",
    "legal",
    "executive",
}
_UNIT_REGISTRY = UnitRegistry()
_LENGTH_DIMENSION = _UNIT_REGISTRY.mm.dimensionality


def _format_magnitude(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.6g}"


def _normalise_dimension(value: Any) -> str:
    """Return a LaTeX dimension string, converting bare numbers to millimetres."""
    if isinstance(value, (int, float)):
        return f"{value}mm"
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        try:
            numeric_value = float(stripped)
        except ValueError:
            numeric_value = None
        else:
            return f"{_format_magnitude(numeric_value)}mm"

        try:
            quantity = _UNIT_REGISTRY(stripped)
        except (UndefinedUnitError, DimensionalityError):
            quantity = None
        else:
            if quantity.check(_LENGTH_DIMENSION):
                converted = quantity.to(_UNIT_REGISTRY.mm).magnitude
                return f"{_format_magnitude(float(converted))}mm"
        try:
            float(stripped)
        except ValueError:
            raise TemplateError(f"Unsupported dimension value '{value}'.") from None
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
            return _normalise_dimension("1.5cm")
        if lowered == "wide":
            return _normalise_dimension("3.0cm")
        dim = _normalise_dimension(cleaned)
        return dim or None
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

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    format: str | None = None
    width: str | None = None
    height: str | None = None
    orientation: Literal["portrait", "landscape"] = "portrait"
    margin: str | dict[str, str] | None = None
    frame: bool = False
    binding_offset: str | None = Field(default=None, alias="binding")
    watermark: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

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
        if "binding" in payload and "binding_offset" not in payload:
            payload["binding_offset"] = payload.pop("binding")
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

    @field_validator("orientation", mode="before")
    @classmethod
    def _format_orientation(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            candidate = value.strip().lower()
            if candidate in {"vertical", "portrait"}:
                return "portrait"
            if candidate in {"horizontal", "landscape"}:
                return "landscape"
        return value

    @field_validator("binding_offset", mode="before")
    @classmethod
    def _format_binding(cls, value: Any) -> str | None:
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

    def geometry_options(self, *, default_margin: str | None = DEFAULT_MARGIN) -> list[str]:
        options: list[str] = []
        margin_value = self.margin or _normalise_margin(default_margin)
        if margin_value:
            if isinstance(margin_value, str):
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
        if self.binding_offset:
            options.append(f"bindingoffset={self.binding_offset}")

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
    geometry_options_list: list[str]
    geometry_extra_options: str
    watermark: str | None
    spec: PaperSpec


def resolve_geometry_settings(
    context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
) -> GeometryResolution:
    """Resolve geometry settings from template context and overrides."""
    press_section = overrides.get("press") if isinstance(overrides, Mapping) else {}
    paper_raw = press_section.get("paper") if isinstance(press_section, Mapping) else None
    geometry_extra = press_section.get("geometry") if isinstance(press_section, Mapping) else None
    margin_raw = press_section.get("margin") if isinstance(press_section, Mapping) else None
    orientation_raw = (
        press_section.get("orientation") if isinstance(press_section, Mapping) else None
    )
    watermark_raw = press_section.get("watermark") if isinstance(press_section, Mapping) else None
    binding_raw = press_section.get("binding") if isinstance(press_section, Mapping) else None
    frame_raw = press_section.get("frame") if isinstance(press_section, Mapping) else None

    if paper_raw is None:
        paper_raw = context.get("paper")
    if geometry_extra is None:
        geometry_extra = context.get("geometry")
    if margin_raw is None:
        margin_raw = context.get("margin")
    if orientation_raw is None:
        orientation_raw = context.get("orientation")
    if watermark_raw is None:
        watermark_raw = context.get("watermark")
    if binding_raw is None:
        binding_raw = context.get("binding")
    if frame_raw is None:
        frame_raw = context.get("frame")

    payload: dict[str, Any] = {}
    if isinstance(paper_raw, Mapping):
        payload.update(paper_raw)
    elif paper_raw is not None:
        payload["format"] = paper_raw

    if "margin" not in payload and margin_raw is not None:
        payload["margin"] = margin_raw
    if "orientation" not in payload and orientation_raw is not None:
        payload["orientation"] = orientation_raw
    if "watermark" not in payload and watermark_raw is not None:
        payload["watermark"] = watermark_raw
    if "binding" not in payload and binding_raw is not None:
        payload["binding"] = binding_raw
    if "frame" not in payload and frame_raw is not None:
        payload["frame"] = frame_raw

    if isinstance(geometry_extra, Mapping):
        formatted_extra: dict[str, Any] = {}
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
        existing_extra = payload.get("extra") if isinstance(payload.get("extra"), Mapping) else {}
        merged_extra = dict(existing_extra)
        merged_extra.update(formatted_extra)
        if merged_extra:
            payload["extra"] = merged_extra

    try:
        spec = PaperSpec.model_validate(payload)
    except ValidationError as exc:
        raise TemplateError(f"Invalid paper settings: {exc}") from exc
    geometry_options_list = spec.geometry_options()
    geometry_options = ",".join(geometry_options_list)
    geometry_extra_options = ",".join(spec.extra_options())
    paper_option, orientation_option = spec.to_documentclass_options()
    options = [opt for opt in (paper_option, orientation_option) if opt]
    documentclass_options = f"[{','.join(options)}]" if options else ""

    return GeometryResolution(
        documentclass_options=documentclass_options,
        paper_option=paper_option,
        orientation_option=orientation_option,
        geometry_options=geometry_options,
        geometry_options_list=geometry_options_list,
        geometry_extra_options=geometry_extra_options,
        watermark=spec.watermark,
        spec=spec,
    )


def inject_geometry_context(
    context: dict[str, Any], overrides: Mapping[str, Any] | None = None
) -> GeometryResolution:
    """Populate a context dictionary with resolved geometry settings."""
    resolution = resolve_geometry_settings(context, overrides)
    context["documentclass_options"] = resolution.documentclass_options
    context["paper_option"] = resolution.paper_option
    context["orientation_option"] = resolution.orientation_option
    context["geometry_options"] = resolution.geometry_options
    context["geometry_options_list"] = resolution.geometry_options_list
    context["geometry_extra_options"] = resolution.geometry_extra_options
    if resolution.watermark:
        context["geometry_watermark"] = resolution.watermark
    else:
        context.pop("geometry_watermark", None)
    return resolution


__all__ = [
    "DEFAULT_MARGIN",
    "GeometryResolution",
    "PaperSpec",
    "inject_geometry_context",
    "resolve_geometry_settings",
]
