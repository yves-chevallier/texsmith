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
    marks: bool = False
    binding_offset: str | None = Field(default=None, alias="binding")
    duplex: bool = True
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
        if "frame" in payload and "marks" not in payload:
            payload["marks"] = payload.pop("frame")
        if "duplex" in payload:
            payload["duplex"] = bool(payload["duplex"])
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

        if self.marks:
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
    duplex: bool
    page_width: str | None
    page_height: str | None
    margin_all: str | None
    margin_left: str | None
    margin_right: str | None
    margin_top: str | None
    margin_bottom: str | None
    margin_inner: str | None
    margin_outer: str | None
    binding_offset: str | None
    spec: PaperSpec


def resolve_geometry_settings(
    context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
) -> GeometryResolution:
    """Resolve geometry settings from template context and overrides."""
    press_section = overrides.get("press") if isinstance(overrides, Mapping) else {}
    documentclass_override = (
        press_section.get("documentclass") if isinstance(press_section, Mapping) else None
    )
    documentclass_context = context.get("documentclass")
    documentclass = documentclass_override or documentclass_context
    is_memoir = str(documentclass).strip().lower() == "memoir" if documentclass else False
    paper_raw = press_section.get("paper") if isinstance(press_section, Mapping) else None
    geometry_extra = press_section.get("geometry") if isinstance(press_section, Mapping) else None
    margin_raw = press_section.get("margin") if isinstance(press_section, Mapping) else None
    orientation_raw = (
        press_section.get("orientation") if isinstance(press_section, Mapping) else None
    )
    watermark_raw = press_section.get("watermark") if isinstance(press_section, Mapping) else None
    duplex_raw = press_section.get("duplex") if isinstance(press_section, Mapping) else None
    binding_raw = press_section.get("binding") if isinstance(press_section, Mapping) else None
    marks_raw = press_section.get("marks") if isinstance(press_section, Mapping) else None

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
    if duplex_raw is None:
        duplex_raw = context.get("duplex")
    if binding_raw is None:
        binding_raw = context.get("binding")
    if marks_raw is None:
        marks_raw = context.get("marks")
    marks_flag = _coerce_marks_flag(marks_raw)

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
    if "duplex" not in payload and duplex_raw is not None:
        payload["duplex"] = duplex_raw
    if "binding" not in payload and binding_raw is not None:
        payload["binding"] = binding_raw
    if "marks" not in payload and marks_flag is not None:
        payload["marks"] = marks_flag

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
    geometry_options_list = spec.geometry_options() if not is_memoir else []
    geometry_options = ",".join(geometry_options_list)
    geometry_extra_options = ",".join(spec.extra_options()) if not is_memoir else ""
    paper_option, orientation_option = spec.to_documentclass_options()
    options: list[str] = []
    if not is_memoir:
        options = [opt for opt in (paper_option, orientation_option) if opt]
        if spec.marks and "showframe" not in options:
            options.append("showframe")
    if spec.duplex and "twoside" not in options:
        options.append("twoside")
    elif not spec.duplex and "twoside" in options:
        pass
    documentclass_options = f"[{','.join(options)}]" if options else ""

    if is_memoir:
        paper_option = None
        orientation_option = None

    page_width, page_height = _resolve_page_dimensions(spec)
    margin_all, margin_left, margin_right, margin_top, margin_bottom = _resolve_margins(spec)
    if all(
        value is None
        for value in (margin_all, margin_left, margin_right, margin_top, margin_bottom)
    ):
        margin_all = "2cm"
    margin_inner = margin_left
    margin_outer = margin_right
    if spec.binding_offset:
        if margin_inner:
            margin_inner = f"\\dimexpr {margin_inner} + {spec.binding_offset}\\relax"
        else:
            margin_inner = spec.binding_offset

    return GeometryResolution(
        documentclass_options=documentclass_options,
        paper_option=paper_option,
        orientation_option=orientation_option,
        geometry_options=geometry_options,
        geometry_options_list=geometry_options_list,
        geometry_extra_options=geometry_extra_options,
        watermark=spec.watermark,
        duplex=bool(spec.duplex),
        page_width=page_width,
        page_height=page_height,
        margin_all=margin_all,
        margin_left=margin_left,
        margin_right=margin_right,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
        margin_inner=margin_inner,
        margin_outer=margin_outer,
        binding_offset=spec.binding_offset,
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
    context["geometry_page_width"] = resolution.page_width
    context["geometry_page_height"] = resolution.page_height
    context["geometry_margin_all"] = resolution.margin_all
    context["geometry_margin_left"] = resolution.margin_left
    context["geometry_margin_right"] = resolution.margin_right
    context["geometry_margin_top"] = resolution.margin_top
    context["geometry_margin_bottom"] = resolution.margin_bottom
    context["geometry_margin_inner"] = resolution.margin_inner
    context["geometry_margin_outer"] = resolution.margin_outer
    context["geometry_binding_offset"] = resolution.binding_offset
    context["geometry_duplex"] = resolution.duplex
    if resolution.watermark:
        context["geometry_watermark"] = resolution.watermark
    else:
        context.pop("geometry_watermark", None)
    return resolution


def _resolve_page_dimensions(spec: PaperSpec) -> tuple[str | None, str | None]:
    """Return paper width/height strings with orientation applied."""
    width = spec.width
    height = spec.height
    if not width or not height:
        format_dims = _format_dimensions(spec.format)
        if format_dims is not None:
            width, height = format_dims
    if spec.orientation == "landscape" and width and height:
        width, height = height, width
    return width, height


def _format_dimensions(format_name: str | None) -> tuple[str, str] | None:
    if not format_name:
        return None
    lookup = format_name.lower()
    sizes_mm: dict[str, tuple[float, float]] = {
        "a0": (841, 1189),
        "a1": (594, 841),
        "a2": (420, 594),
        "a3": (297, 420),
        "a4": (210, 297),
        "a5": (148, 210),
        "a6": (105, 148),
        "b0": (1000, 1414),
        "b1": (707, 1000),
        "b2": (500, 707),
        "b3": (353, 500),
        "b4": (250, 353),
        "b5": (176, 250),
        "b6": (125, 176),
        "c0": (917, 1297),
        "c1": (648, 917),
        "c2": (458, 648),
        "c3": (324, 458),
        "c4": (229, 324),
        "c5": (162, 229),
        "c6": (114, 162),
        "letter": (215.9, 279.4),
        "legal": (215.9, 355.6),
        "executive": (184.15, 266.7),
    }
    dims = sizes_mm.get(lookup)
    if dims is None:
        return None
    width, height = dims
    return (f"{width}mm", f"{height}mm")


def _resolve_margins(
    spec: PaperSpec,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    margin_all: str | None = None
    margin_left: str | None = None
    margin_right: str | None = None
    margin_top: str | None = None
    margin_bottom: str | None = None
    if isinstance(spec.margin, str):
        margin_all = spec.margin
    elif isinstance(spec.margin, dict):
        margin_left = spec.margin.get("left") or spec.margin.get("l")
        margin_right = spec.margin.get("right") or spec.margin.get("r")
        margin_top = spec.margin.get("top") or spec.margin.get("t")
        margin_bottom = spec.margin.get("bottom") or spec.margin.get("b")
        margin_inner = spec.margin.get("inner")
        margin_outer = spec.margin.get("outer")
        margin_left = margin_inner or margin_left
        margin_right = margin_outer or margin_right
    return margin_all, margin_left, margin_right, margin_top, margin_bottom


def _coerce_marks_flag(value: Any) -> bool | None:
    """Return a boolean marks flag when the payload resembles one."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if not token or token in {"false", "no", "off", "0", "none"}:
            return False
        if token in {"true", "yes", "on", "1", "showframe"}:
            return True
    return None


__all__ = [
    "DEFAULT_MARGIN",
    "GeometryResolution",
    "PaperSpec",
    "inject_geometry_context",
    "resolve_geometry_settings",
]
