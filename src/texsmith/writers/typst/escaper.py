"""Typst escaping (Typst backend responsibility).

Typst markup has a different set of special characters from LaTeX. In Typst
*markup* mode the following characters carry syntactic meaning and must be
backslash-escaped to appear literally:

``\\`` ``#`` ``$`` ``*`` ``_`` `````` ``` (backtick) ``<`` ``>`` ``@`` ``[`` ``]``

(see the Typst syntax reference). A backslash followed by such a character is
rendered as the literal character. We also neutralise a couple of constructs
that Typst would otherwise interpret as markup at the *start* of content:
``-``/``+``/``/`` list markers and ``=`` headings are only special at line
start, but escaping them everywhere is safe and keeps the emitter simple.

The writer escapes the body; what stays here is what the Python side still
interpolates into the template scaffolding, plus :func:`citation_label`, the
label sanitisation the written ``.bib`` has to agree with.
"""

from __future__ import annotations

import re


# Characters that are always syntactically meaningful in Typst markup and must
# be escaped to render literally.
_ESCAPE_CHARS = frozenset("\\#$*_`<>@[]")


def escape_typst_chars(text: str) -> str:
    """Backslash-escape Typst markup special characters in ``text``.

    A single pass over the string; ``\\`` is escaped first implicitly because it
    is a member of :data:`_ESCAPE_CHARS` and each match is prefixed with one
    backslash.
    """
    if not text:
        return text
    out: list[str] = []
    for char in text:
        if char in _ESCAPE_CHARS:
            out.append("\\")
        out.append(char)
    return "".join(out)


#: Typst label syntax (``<...>``) admits only these characters.
_LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]")


def citation_label(key: str) -> str:
    """Map a bibliography key to a Typst label (``<...>``).

    Typst label syntax forbids whitespace and most punctuation; bibliography
    keys are sanitised the same way the ``.bib`` is normalised so ``@key`` and
    ``<key>`` agree with what the writer emitted.
    """
    return _LABEL_SAFE_RE.sub("-", key.strip())


__all__ = ["citation_label", "escape_typst_chars"]
