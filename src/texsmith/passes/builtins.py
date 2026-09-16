"""Import every bundled pass module so that its ``PassSpec`` is registered."""

from __future__ import annotations

from texsmith.passes import (  # noqa: F401
    assets,
    doi,
    emoji,
    epigraph,
    headings,
    highlight,
    include,
    scripts,
    slots,
    snippet,
    title,
    var,
)
