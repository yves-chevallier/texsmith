"""The TeX logo catalogue.

What is left of the ``texlogos`` Markdown extension after phase 5: the specs
themselves. :mod:`texsmith.readers.html` keys its inline lowering on them so a
``LaTeX`` or ``XeLaTeX`` word in an HTML page still becomes the logo macro.
"""

from __future__ import annotations

from .specs import LogoSpec, iter_specs


__all__ = ["LogoSpec", "iter_specs"]
