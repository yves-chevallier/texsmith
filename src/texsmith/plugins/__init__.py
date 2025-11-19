"""Compatibility layer exposing plugin integrations to documentation.

TeXSmith consolidated its plugin utilities under
``texsmith.adapters.plugins``.  mkdocstrings still references the historical
``texsmith.plugins`` namespace, so we re-export the maintained modules here to
keep the public import path available.
"""

from __future__ import annotations

from texsmith.adapters.plugins import material, snippet


__all__ = ["material", "snippet"]
