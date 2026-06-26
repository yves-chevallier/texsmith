"""TeXSmith's bundled Python-Markdown extensions.

Each submodule ships a ``markdown.Extension`` (and, for ``index``, an MkDocs
plugin). The authoritative list of extensions enabled by the conversion
pipeline lives in
:data:`texsmith.adapters.markdown.DEFAULT_MARKDOWN_EXTENSIONS`; the same entries
are also exposed to third-party Markdown/MkDocs setups via the entry points
declared in ``pyproject.toml``.
"""

from __future__ import annotations
