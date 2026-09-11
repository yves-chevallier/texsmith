"""Deprecation aliases of the ``texsmith.counters`` and ``texsmith.index`` plugins.

Both jobs — site-wide counters and index entries in the search index — are
done by the ``texsmith`` plugin now (``specs/migration/web-profile.md``).
The two entry points stay one release so an existing ``mkdocs.yml`` keeps
loading: each logs a warning naming the replacement and does nothing.
Removed in 0.8.
"""

from __future__ import annotations

from mkdocs.config import config_options
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin
from mkdocs.utils import log


__all__ = ["CountersAliasPlugin", "IndexAliasPlugin"]


class _AliasPlugin(BasePlugin):
    """A plugin that only says what replaced it."""

    former: str = ""
    hint: str = ""

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:
        log.warning(
            "The '%s' plugin is deprecated and does nothing: the 'texsmith' plugin %s. "
            "Remove it from 'plugins' in mkdocs.yml; "
            "the entry point disappears in 0.8.",
            self.former,
            self.hint,
        )
        return config


class CountersAliasPlugin(_AliasPlugin):
    """``plugins: - texsmith.counters``: declare counters under ``texsmith.declare``."""

    former = "texsmith.counters"
    hint = "numbers every counter site-wide (declare them under 'declare.counters')"

    config_scheme = (
        ("inject_markdown_extension", config_options.Type(bool, default=True)),
        ("inject_reference_extension", config_options.Type(bool, default=True)),
        ("counters", config_options.Type(dict, default={})),
    )


class IndexAliasPlugin(_AliasPlugin):
    """``plugins: - texsmith.index``: the ``texsmith`` plugin feeds the search index."""

    former = "texsmith.index"
    hint = "injects the index entries into the search index"

    config_scheme = (
        ("inject_markdown_extension", config_options.Type(bool, default=True)),
    )
