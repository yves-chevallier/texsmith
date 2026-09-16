"""Fix-ups the rendered HTML of a page needs, shared by both site integrations.

MkDocs runs them from the plugin's ``on_post_page``, Zensical from a
postprocessor of :mod:`texsmith.site.web`; the rendering underneath is the
same Python-Markdown, so the corrections are one implementation.
"""

from __future__ import annotations

import re


__all__ = ["unescape_table_pipes"]

#: One table cell, its opening tag to the matching closing one. Cells do not
#: nest, so the non-greedy match cannot run past the end of its own.
_CELL_RE = re.compile(r"<(t[dh])\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
#: A code span inside such a cell.
_CODE_RE = re.compile(r"(<code\b[^>]*>)(.*?)(</code>)", re.IGNORECASE | re.DOTALL)


def _unescape_cell(match: re.Match[str]) -> str:
    """Return one table cell with the pipes of its code spans unescaped."""
    return _CODE_RE.sub(
        lambda code: code.group(1) + code.group(2).replace("\\|", "|") + code.group(3),
        match.group(0),
    )


def unescape_table_pipes(html: str) -> str:
    r"""Turn ``\|`` back into ``|`` inside the code spans of a table cell.

    GFM and TMark both want ``\|`` for a pipe that must stay inside a cell,
    code span included, and the lowering leaves the escape for the Markdown
    renderer to remove. Python-Markdown's ``tables`` extension only half does
    it: ``TableProcessor.RE_CODE_PIPES`` marks the pipes of a code span so
    ``_split`` does not break the row there, but it slices the *raw* row and
    the code span is atomic from then on — so the page shows ``x \| y`` where
    the author wrote ``x | y``. Outside a cell the backslash is meaningful, a
    literal one before a pipe, which is why only cells are touched.
    """
    if "\\|" not in html:
        return html
    return _CELL_RE.sub(_unescape_cell, html)
