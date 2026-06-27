"""TeXSmith extension providing extra TeX logo commands."""

from __future__ import annotations

from .markdown import TexLogosExtension, makeExtension
from .specs import LogoSpec, iter_specs


__all__ = ["LogoSpec", "TexLogosExtension", "iter_specs", "makeExtension"]
