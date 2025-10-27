"""Compatibility package for :mod:`texsmith.adapters.markdown`."""

from __future__ import annotations

import sys

from ..adapters import markdown as _markdown

sys.modules[__name__] = _markdown
