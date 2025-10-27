"""Compatibility package for :mod:`texsmith.domain.templates`."""

from __future__ import annotations

import sys

from ..domain import templates as _templates

sys.modules[__name__] = _templates
