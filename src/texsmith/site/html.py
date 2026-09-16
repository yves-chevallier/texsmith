"""Fix-ups the rendered HTML of a page needs, shared by both site integrations.

MkDocs runs them from the plugin's ``on_post_page``, Zensical from a
postprocessor of :mod:`texsmith.site.web`; the rendering underneath is the
same Python-Markdown, so the corrections are one implementation.

Each is a pure function over the HTML of a page: nothing here reads the
site, the configuration or the file system, which is what lets the two
integrations share them and the tests state them in one line.
"""

from __future__ import annotations

import re


__all__ = ["NNBSP", "french_typography", "unescape_table_pipes"]

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


#: The narrow no-break space French typography asks for before a double
#: punctuation mark and inside guillemets (U+202F). The retired hook this
#: comes from wrote ``&thinsp;``, a *breaking* thin space, which lets a line
#: end on the word and start on the ``?``; the width is the same, the break
#: is not.
NNBSP = "\u202f"

#: What the rules never see, in the order the alternatives have to be tried:
#: a ``code``, ``pre``, ``script`` or ``style`` element with its content, a
#: comment, any other tag — so every attribute value with it — and a
#: character entity, whose own ``;`` would otherwise read as punctuation and
#: whose ``&nbsp;`` is a space the author already chose.
_OPAQUE_RE = re.compile(
    r"<(code|pre|script|style)\b[^>]*>.*?</\1\s*>"
    r"|<!--.*?-->"
    r"|<[^>]*>"
    r"|&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);",
    re.IGNORECASE | re.DOTALL,
)

#: A double punctuation mark to space out: after a word — or after what
#: closes one, a guillemet the quote rule just wrote, a parenthesis, a
#: bracket — over at most the ordinary space the author typed. A mark
#: followed by a word character or a slash belongs to a token rather than to
#: a sentence (``https://``, ``12:30``, ``?page=2``), and a mark already
#: preceded by a space of its own, no-break or narrow, fails the lookbehind,
#: which is what makes the rule idempotent over a page that ran through it
#: before.
_FRENCH_PUNCTUATION_RE = re.compile(r"(?<=[\w\u00bb)\]]) ?([;:!?])(?![\w/])")

#: The same mark opening a text node, where the lookbehind above has nothing
#: to look at: the word it follows is the last one of the element that just
#: closed. ``**Note** : ...`` is the shape, and it is a common one.
_FRENCH_LEADING_RE = re.compile(r"^ ?([;:!?])(?![\w/])")

#: An element closing right before such a text node — the one tag after
#: which a leading mark still punctuates a word.
_CLOSING_TAG_RE = re.compile(r"</[A-Za-z][^>]*>\s*$")

#: A run between two straight double quotes, inside one text node.
_FRENCH_QUOTES_RE = re.compile(r'"([^"]+)"')


def _french_text(text: str, *, after_close: bool) -> str:
    """Apply the French rules to one text node."""
    if after_close:
        text = _FRENCH_LEADING_RE.sub(NNBSP + r"\1", text)
    # The quotes first: the guillemet they leave behind is a word's end as
    # far as the next rule is concerned, so ``"un test" ;`` is spaced too.
    quoted = _FRENCH_QUOTES_RE.sub("\u00ab" + NNBSP + r"\1" + NNBSP + "\u00bb", text)
    return _FRENCH_PUNCTUATION_RE.sub(NNBSP + r"\1", quoted)


def french_typography(html: str) -> str:
    """Space the punctuation of a rendered page the French way.

    Two rules, the ones the handbook's ``hooks/french.py`` applied before
    TeXSmith took the page over: a narrow no-break space before ``;``,
    ``:``, ``!`` and ``?``, and ``"..."`` turned into ``« ... »`` with the
    same space inside the guillemets. ``babel-french`` does as much for the
    PDF, where the engine spaces the punctuation itself; the browser does
    nothing of the sort, so the page carries the spaces as characters.

    Only text nodes are touched: ``_OPAQUE_RE`` holds the code, the tags —
    attribute values with them — and the entities out of the way, so a class
    name, a URL or an ``&nbsp;`` the author wrote comes out as it went in.
    Which is why a node knows whether an element closed just before it: the
    word a leading mark punctuates is then in the node before, out of reach.
    """
    out: list[str] = []
    end = 0
    after_close = False
    for match in _OPAQUE_RE.finditer(html):
        out.append(_french_text(html[end : match.start()], after_close=after_close))
        opaque = match.group(0)
        out.append(opaque)
        after_close = _CLOSING_TAG_RE.search(opaque) is not None
        end = match.end()
    out.append(_french_text(html[end:], after_close=after_close))
    return "".join(out)
