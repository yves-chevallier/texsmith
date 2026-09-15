"""What a site generator drives when it renders a TeXSmith site.

MkDocs reaches this package through its plugin, Zensical through a
Python-Markdown extension and a ``texsmith site`` command, because Zensical
has no plugin hooks at all. Neither generator is imported here: the package
holds the site index (the cross-page pre-pass, the label map and the
per-page lowering onto ``tmark.lower_web``), the reader for ``mkdocs.yml``
and ``zensical.toml``, and — as the migration proceeds — the navigation
resolver and the Markdown extension that the generators wire up.
"""

from __future__ import annotations

from texsmith.site.config import SiteConfig, load_site_config
from texsmith.site.index import LoweredPage, PageRecord, SiteIndex, SitePage


__all__ = [
    "LoweredPage",
    "PageRecord",
    "SiteConfig",
    "SiteIndex",
    "SitePage",
    "load_site_config",
]
