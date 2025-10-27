"""Compatibility package for :mod:`texsmith.domain.bibliography`."""

from __future__ import annotations

import sys

from ..domain import bibliography as _bibliography

sys.modules[__name__] = _bibliography
