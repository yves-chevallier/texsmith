"""Compatibility wrapper for :mod:`texsmith.adapters.latex.templates`."""

from __future__ import annotations

import sys

from ...adapters.latex import templates as _templates

sys.modules[__name__] = _templates
