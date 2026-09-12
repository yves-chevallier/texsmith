"""What is left of TeXSmith's bundled Markdown extensions.

The 17 Python-Markdown extensions are gone with the Python-Markdown pipeline
(phase 5 of ``specs/tmark-migration.md``): tmark parses every Markdown source
and its registries own the constructs they used to add. Two data modules
survive because :mod:`texsmith.readers.html` — the reader for ``.html`` input
and the MkDocs ``press.reader: html`` fallback — still needs them:

* :mod:`texsmith.extensions.tables` — the validated table model an HTML
  ``<table>`` is rebuilt into before it becomes a ``TableModel``;
* :mod:`texsmith.extensions.texlogos` — the TeX logo catalogue the inline
  lowering keys on.
"""

from __future__ import annotations
