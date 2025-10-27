"""Compatibility package for :mod:`texsmith.adapters.latex`."""

from __future__ import annotations

import sys

from ..adapters import latex as _latex

sys.modules[__name__] = _latex
