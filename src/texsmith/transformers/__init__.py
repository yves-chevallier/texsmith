"""Compatibility package for :mod:`texsmith.adapters.transformers`."""

from __future__ import annotations

import sys

from ..adapters import transformers as _transformers


sys.modules[__name__] = _transformers
