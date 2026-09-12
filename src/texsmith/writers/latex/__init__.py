"""What the LaTeX backend still owns on the Python side.

``tmark.write(…, "latex")`` emits the bodies; what stays here is the work a
writer cannot do from Rust: :mod:`~texsmith.writers.latex.assets` stores and
converts the files an ``Image`` points at (the ``assets`` pass drives it) and
:mod:`~texsmith.writers.latex.escaper` remains the single source of truth for
LaTeX escaping that the templates, the fonts and the fragments reach through
:mod:`texsmith.adapters.latex.utils`.
"""

from __future__ import annotations

from .escaper import escape_latex_chars


__all__ = ["escape_latex_chars"]
