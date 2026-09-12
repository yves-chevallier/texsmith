"""What the Typst backend still owns on the Python side.

``tmark.write(…, "typst")`` emits the bodies; what stays here is the work a
writer cannot do from Rust: :mod:`~texsmith.writers.typst.document` wraps a body
in the standalone preamble, :mod:`~texsmith.writers.typst.build` runs the
compiler, and :mod:`~texsmith.writers.typst.escaper` escapes the strings the
template scaffolding interpolates.
"""

from __future__ import annotations

from .document import render_document
from .escaper import escape_typst_chars


__all__ = ["escape_typst_chars", "render_document"]
