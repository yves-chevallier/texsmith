"""TeXSmith extension providing extra TeX logo commands."""

from __future__ import annotations

from .renderer import register as register_renderer
from .specs import LogoSpec, iter_specs

__all__ = ["register_renderer", "LogoSpec", "iter_specs"]
