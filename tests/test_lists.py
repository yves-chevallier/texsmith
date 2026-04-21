"""Tests for list rendering in the LaTeX adapter."""

from __future__ import annotations

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown


def _render(md: str) -> str:
    html = render_markdown(md, extensions=DEFAULT_MARKDOWN_EXTENSIONS).html
    return LaTeXRenderer().render(html)


# ---------------------------------------------------------------------------
# Flat / tight lists
# ---------------------------------------------------------------------------


def test_simple_unordered_list() -> None:
    latex = _render("- Item 1\n- Item 2\n- Item 3\n")
    assert r"\begin{itemize}" in latex
    assert r"\item{} Item 1" in latex
    assert r"\item{} Item 2" in latex
    assert r"\item{} Item 3" in latex
    assert r"\end{itemize}" in latex


def test_simple_ordered_list() -> None:
    latex = _render("1. First\n2. Second\n3. Third\n")
    assert r"\begin{enumerate}" in latex
    assert r"\item First" in latex
    assert r"\item Second" in latex
    assert r"\end{enumerate}" in latex


# ---------------------------------------------------------------------------
# Nested lists
# ---------------------------------------------------------------------------


def test_nested_unordered_list_structure() -> None:
    md = "- Parent\n    - Child 1\n    - Child 2\n"
    latex = _render(md)
    assert latex.count(r"\begin{itemize}") == 2
    assert latex.count(r"\end{itemize}") == 2
    assert r"\item{} Child 1" in latex
    assert r"\item{} Child 2" in latex


def test_nested_list_starts_on_new_line() -> None:
    """The inner \\begin{itemize} must not be glued to the parent item text."""
    md = "- Parent\n    - Child 1\n    - Child 2\n"
    latex = _render(md)
    # \begin{itemize} must be preceded by a newline, not by the parent text
    assert r"Parent\begin{itemize}" not in latex
    assert "Parent\n" in latex or "Parent" in latex  # text present
    # Locate relative positions
    parent_pos = latex.index(r"\item{} Parent")
    inner_begin_pos = latex.index(r"\begin{itemize}", parent_pos + 1)
    text_between = latex[parent_pos:inner_begin_pos]
    assert "\n" in text_between, "Expected newline between parent item and nested \\begin{itemize}"


def test_nested_ordered_list_starts_on_new_line() -> None:
    md = "1. Parent\n    1. Child\n"
    latex = _render(md)
    assert r"Parent\begin{enumerate}" not in latex


def test_deeply_nested_list() -> None:
    md = "- L1\n    - L2\n        - L3\n"
    latex = _render(md)
    assert latex.count(r"\begin{itemize}") == 3
    assert r"\item{} L3" in latex


# ---------------------------------------------------------------------------
# 2-space indentation: Python-Markdown requires 4 spaces
# (documented behaviour, not a TeXSmith bug)
# ---------------------------------------------------------------------------


def test_two_space_indent_is_flat_in_python_markdown() -> None:
    """Python-Markdown requires 4-space indentation for sub-lists.

    With only 2 spaces, items are rendered as siblings at the same level.
    This matches Python-Markdown's documented behaviour (not CommonMark).
    """
    md = "- Parent\n  - Not a child (2-space indent)\n"
    latex = _render(md)
    # Only one itemize environment (flat list)
    assert latex.count(r"\begin{itemize}") == 1


# ---------------------------------------------------------------------------
# Mixed nested / flat
# ---------------------------------------------------------------------------


def test_sibling_after_nested_list() -> None:
    md = "- A\n    - A1\n- B\n"
    latex = _render(md)
    assert r"\item{} A" in latex
    assert r"\item{} A1" in latex
    assert r"\item{} B" in latex
    # Outer list wraps all three
    assert latex.count(r"\begin{itemize}") == 2


def test_nested_list_item_text_preserved() -> None:
    md = "- Hello world\n    - Nested\n"
    latex = _render(md)
    assert "Hello world" in latex
    assert "Nested" in latex
