"""Compatibility façade that re-exports the conversion package symbols."""

from __future__ import annotations

from importlib import import_module as _import_module

_facade = _import_module(".domain.conversion", __package__)

__all__ = getattr(_facade, "__all__", [])

for name in __all__:
    globals()[name] = getattr(_facade, name)

# Preserve relaxed attribute access for compatibility with existing monkeypatches.
if hasattr(_facade, "DoiBibliographyFetcher"):
    DoiBibliographyFetcher = _facade.DoiBibliographyFetcher
