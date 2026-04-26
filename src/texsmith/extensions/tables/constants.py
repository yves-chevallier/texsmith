"""Shared constants for the yaml-table extension.

Centralises the string literals, regular expressions, alignment mappings and
Markdown-pipeline priorities used across :mod:`.schema`, :mod:`.layout`,
:mod:`.html`, :mod:`.renderer` and :mod:`.markdown`. Keeping them in a single
module turns the HTML/LaTeX contract into a type-checked surface and makes
pipeline priorities explicit instead of scattered magic numbers.
"""

from __future__ import annotations

import re
import sys
from typing import Final


if sys.version_info >= (3, 11):
    from enum import StrEnum
else:  # pragma: no cover - 3.10 polyfill
    from enum import Enum

    class StrEnum(str, Enum):
        """Minimal backport of :class:`enum.StrEnum` for Python 3.10.

        ``str(member)`` already returns the value because the class inherits from
        ``str``; that is the only behaviour we rely on for ``data-ts-*`` attribute
        names.
        """

        def __str__(self) -> str:
            return str.__str__(self)


# ---------------------------------------------------------------------------
# HTML contract: data-ts-* attributes
# ---------------------------------------------------------------------------


class TableAttr(StrEnum):
    """``data-ts-*`` attributes attached to ``<table>`` and its descendants.

    Writers (``html.py``, the table-config treeprocessor) and readers
    (``renderer.py``) must use these constants rather than string literals so
    the HTML shape stays a single source of truth.
    """

    TABLE = "data-ts-table"
    """Marker ``"1"`` on tables rendered by this extension (yaml or md+config)."""

    ENV = "data-ts-env"
    """Chosen LaTeX environment: ``tabular`` / ``tabularx`` / ``longtable``."""

    COLSPEC = "data-ts-colspec"
    """Complete LaTeX column preamble (e.g. ``lrX`` or ``>{…}p{…}c``)."""

    WIDTH = "data-ts-width"
    """Total width argument for ``tabularx`` / ``longtable``."""

    PLACEMENT = "data-ts-placement"
    """Float placement specifier (``htbp!`` etc.)."""

    ALIGN = "data-ts-align"
    """Per-cell alignment override, short form (``l`` / ``c`` / ``r`` / ``j``)."""

    ROLE = "data-ts-role"
    """Row role: ``header`` / ``body`` / ``footer`` / ``separator``."""

    RULE = "data-ts-rule"
    """Horizontal rule style, currently only ``"double"``."""

    SEP_LABEL = "data-ts-sep-label"
    """Optional label displayed on a separator row."""

    EMPTY = "data-ts-empty"
    """Marker ``"1"`` on cells whose original value was ``None``."""


# ---------------------------------------------------------------------------
# Width: percentage literal
# ---------------------------------------------------------------------------


PERCENT_RE: Final = re.compile(r"^(\d+(?:\.\d+)?)%$")
"""Match ``"50%"``, ``"33.3%"``, etc. The group captures the numeric part."""


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------


ALIGN_ALIASES: Final[dict[str, str]] = {
    "l": "l",
    "left": "l",
    "c": "c",
    "center": "c",
    "centre": "c",
    "r": "r",
    "right": "r",
    "j": "j",
    "justify": "j",
    "justified": "j",
}
"""User-friendly long forms accepted everywhere an ``align`` value is allowed.
All values normalise to a one-letter form (``l``/``c``/``r``/``j``).
"""


ALIGN_WRAPPERS: Final[dict[str, str]] = {
    "l": r">{\raggedright\arraybackslash}",
    "r": r">{\raggedleft\arraybackslash}",
    "c": r">{\centering\arraybackslash}",
    "j": "",
}
"""LaTeX preamble prefix applied to a ``p{…}``/``X`` column per alignment.
``j`` (justify) needs no wrapper since ``p{…}`` / ``X`` justify by default.
"""


# ---------------------------------------------------------------------------
# Markdown pipeline priorities
# ---------------------------------------------------------------------------


class Priority:
    """Markdown pipeline priorities for the yaml-table handlers.

    Python-Markdown orders preprocessors, block processors and treeprocessors
    by priority: **higher values run first**. The numbers below straddle
    third-party handlers we depend on, so changing them or upgrading a
    dependency may require revisiting these values.

    Cross-references:

    - ``pymdownx.superfences`` ships ``fenced_raw_block`` at ``31.05``. Our
      ``TABLE_CONFIG_PRE`` (32) must outrank it so a ``yaml table-config``
      fence is consumed before superfences misparses it; ``YAML_TABLE_PRE``
      (29) is happy to run afterwards because superfences passes ``yaml``
      fences through untouched.
    - ``CAPTION_TREE`` (5) must outrank ``CONFIG_TREE`` (4) so that the
      caption is attached to the table before table-config binding runs.
    - ``SEPARATOR_TREE`` (17) must outrank ``texsmith_smart_dashes`` (16):
      dash-only rows are detected on the original ASCII hyphens, before
      smart-dashes rewrites them into em/en-dashes which would defeat the
      ``-{3,}`` match.
    """

    YAML_TABLE_PRE: Final = 29
    TABLE_CONFIG_PRE: Final = 32
    TABLE_CONFIG_BLOCK: Final = 180
    CAPTION_TREE: Final = 5
    CONFIG_TREE: Final = 4
    SEPARATOR_TREE: Final = 17
    RENDERER: Final = 35


__all__ = [
    "ALIGN_ALIASES",
    "ALIGN_WRAPPERS",
    "PERCENT_RE",
    "Priority",
    "TableAttr",
]
