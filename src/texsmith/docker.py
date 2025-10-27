"""Compatibility shim for :mod:`texsmith.adapters.docker`."""

from __future__ import annotations

import sys

from .adapters import docker as _docker

globals().update(vars(_docker))
sys.modules[__name__] = _docker
