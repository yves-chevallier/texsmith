"""Public entry points for the TeX logo Markdown and LaTeX extension."""

from __future__ import annotations

from .extensions.texlogos import LogoSpec, iter_specs, register_renderer
from .extensions.texlogos.markdown import TexLogosExtension, makeExtension


__all__ = [
    "LogoSpec",
    "TexLogosExtension",
    "iter_specs",
    "makeExtension",
    "register_renderer",
]
