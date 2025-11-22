from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from texsmith.core.fragments import FragmentDefinition, FragmentPiece
from texsmith.core.paper import PaperSpec


class GeometryFragmentConfig(BaseModel):
    """Pydantic schema scoping the geometry section of front matter."""

    paper: Any | None = None
    geometry: dict[str, Any] = Field(default_factory=dict)
    margin: Any | None = None

    model_config = {"extra": "allow"}


def create_fragment() -> FragmentDefinition:
    """
    Return the geometry fragment definition with inline package setup.

    The fragment expects geometry-related context (paper/margin/geometry options)
    already resolved in the template context. It uses ``PaperSpec`` to validate
    any provided payload when invoked programmatically by extensions.
    """
    template_path = Path(__file__).with_name("ts_geometry.tex.jinja")
    return FragmentDefinition(
        name="ts-geometry",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="inline",
                slot="geometry_setup",
            )
        ],
        description="Page layout setup driven by press.paper.",
        source=template_path,
    )


__all__ = ["GeometryFragmentConfig", "create_fragment"]
