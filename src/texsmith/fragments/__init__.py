"""Legacy fragment namespace.

Fragments now register via ``fragment.toml`` or entry points returning
``Fragment``/``FragmentDefinition`` objects. This module is kept only to avoid
import errors for legacy paths; no registration occurs here.
"""

from __future__ import annotations


__all__ = []
