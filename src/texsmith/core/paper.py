"""Backward-compatible shim for geometry helpers.

The actual implementation now lives under
``texsmith.builtin_fragments.ts_geometry.paper`` so that geometry logic stays
co-located with the ts-geometry fragment. This module re-exports the helpers
for existing imports.
"""

from texsmith.builtin_fragments.ts_geometry.paper import *
