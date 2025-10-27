"""Compatibility package for :mod:`texsmith.domain.conversion`."""

from __future__ import annotations

import sys

from ..domain import conversion as _conversion

sys.modules[__name__] = _conversion
