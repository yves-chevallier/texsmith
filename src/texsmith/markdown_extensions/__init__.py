"""Compatibility package for :mod:`texsmith.adapters.markdown_extensions`."""

from __future__ import annotations

import sys

from ..adapters import markdown_extensions as _markdown_extensions

sys.modules[__name__] = _markdown_extensions
