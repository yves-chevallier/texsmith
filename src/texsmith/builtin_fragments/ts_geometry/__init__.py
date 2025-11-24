from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from texsmith.core.fragments import FragmentDefinition, FragmentPiece
from texsmith.core.templates.base import _build_environment

from .paper import GeometryResolution, inject_geometry_context, resolve_geometry_settings


class GeometryFragmentConfig(BaseModel):
    """Validated payload accepted by the ts-geometry fragment."""

    paper: Mapping[str, Any] | None = None
    geometry: dict[str, Any] = Field(default_factory=dict)
    margin: Any | None = None
    orientation: Any | None = None
    binding: Any | None = None
    frame: bool | None = None
    watermark: str | None = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _fold_paper(cls, data: Any) -> Any:
        if data is None:
            return {}
        if not isinstance(data, Mapping):
            return {"paper": data}

        payload = dict(data)
        paper_payload = payload.get("paper")
        if isinstance(paper_payload, Mapping):
            paper_data: dict[str, Any] = dict(paper_payload)
        elif paper_payload is None:
            paper_data = {}
        else:
            paper_data = {"format": paper_payload}

        for key in ("margin", "orientation", "binding", "frame", "watermark"):
            if key in payload and key not in paper_data:
                paper_data[key] = payload[key]

        extra_payload = payload.get("geometry") or payload.get("extra")
        if isinstance(extra_payload, Mapping):
            merged_extra = dict(paper_data.get("extra") or {})
            merged_extra.update(extra_payload)
            paper_data["extra"] = merged_extra

        payload["paper"] = paper_data
        return payload

    def to_context(self) -> dict[str, Any]:
        """Return a context mapping suitable for ``resolve_geometry_settings``."""
        context: dict[str, Any] = {}
        if self.paper is not None:
            context["paper"] = self.paper
        if self.geometry:
            context["geometry"] = self.geometry
        if self.margin is not None:
            context["margin"] = self.margin
        if self.orientation is not None:
            context["orientation"] = self.orientation
        if self.binding is not None:
            context["binding"] = self.binding
        if self.frame is not None:
            context["frame"] = self.frame
        if self.watermark is not None:
            context["watermark"] = self.watermark
        return context

    def resolve(self) -> GeometryResolution:
        """Return a resolved geometry payload for this configuration."""
        return resolve_geometry_settings(self.to_context())


class GeometryFragment:
    """Programmatic renderer for the ts-geometry fragment."""

    def __init__(self, payload: Any | None = None) -> None:
        self.config = GeometryFragmentConfig.model_validate(payload or {})
        self.template_path = Path(__file__).with_name("ts_geometry.tex.jinja")

    def render(self) -> str:
        context = self.config.to_context()
        inject_geometry_context(context)  # populates geometry_* keys
        environment = _build_environment(self.template_path.parent)
        template = environment.get_template(self.template_path.name)
        return template.render(**context)

    def get_latex(self) -> str:
        """Return the rendered LaTeX fragment."""
        return self.render()

    def getLatex(self) -> str:  # noqa: N802 - API compatibility
        """CamelCase alias for front-end callers."""
        return self.render()


def create_fragment() -> FragmentDefinition:
    """Return the geometry fragment definition injected via ``extra_packages``."""
    template_path = Path(__file__).with_name("ts_geometry.tex.jinja")
    return FragmentDefinition(
        name="ts-geometry",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="inline",
                slot="extra_packages",
            )
        ],
        description="Page layout setup driven by press.paper.",
        source=template_path,
        context_defaults={
            "extra_packages": "",
            "documentclass_options": "",
            "geometry_options": "",
            "geometry_options_list": [],
            "geometry_extra_options": "",
            "paper": {"format": "a4"},
        },
        context_injector=lambda context, overrides=None: inject_geometry_context(
            context, overrides
        ),
    )


__all__ = ["GeometryFragment", "GeometryFragmentConfig", "create_fragment"]
