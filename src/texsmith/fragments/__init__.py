"""Bundled TeXSmith fragments.

Each subpackage ships a ``fragment.toml`` manifest plus a ``Fragment``/
``FragmentDefinition`` object; they are discovered by
:class:`texsmith.core.fragments.FragmentRegistry` via filesystem scanning of
``FRAGMENT_ROOT`` and the ``texsmith.fragments`` entry-point group. This module
holds no registration logic itself.
"""

from __future__ import annotations


__all__: list[str] = []
