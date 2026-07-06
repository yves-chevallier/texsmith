"""Tests for the ``@[label]`` / ``@label`` cross-reference shorthand."""

from __future__ import annotations

from bs4 import BeautifulSoup

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown


def _render(source: str) -> BeautifulSoup:
    html = render_markdown(source, extensions=DEFAULT_MARKDOWN_EXTENSIONS).html
    return BeautifulSoup(html, "html.parser")


def test_bracketed_reference_becomes_anchor() -> None:
    soup = _render("Voir la section @[sec:interruptions] pour le détail.")
    anchor = soup.find("a", href="#sec:interruptions")
    assert anchor is not None
    assert anchor.get_text() == ""
    assert "@[" not in soup.get_text()


def test_bare_reference_single_word() -> None:
    soup = _render("Le tableau @tbl:constats en dresse la liste.")
    assert soup.find("a", href="#tbl:constats") is not None


def test_bare_reference_excludes_sentence_punctuation() -> None:
    soup = _render("évoquée en @sec:interruptions. Par ailleurs...")
    assert soup.find("a", href="#sec:interruptions") is not None
    assert soup.get_text().startswith("évoquée en . Par")


def test_bare_reference_without_colon() -> None:
    soup = _render("From @pythagoras, we know that...")
    assert soup.find("a", href="#pythagoras") is not None


def test_email_addresses_are_not_references() -> None:
    soup = _render("Contact john.doe@example.com for details.")
    assert soup.find("a", href="#example.com") is None


def test_url_at_segments_are_not_references() -> None:
    soup = _render("Profile at `https://social.example/@user` here.")
    assert soup.find("a", href="#user") is None


def test_code_spans_are_untouched() -> None:
    soup = _render("Use `@[label]` to reference.")
    code = soup.find("code")
    assert code is not None
    assert code.get_text() == "@[label]"
    assert soup.find("a") is None


def test_escaped_at_stays_literal() -> None:
    soup = _render("A literal \\@sec:intro stays.")
    assert soup.find("a") is None
    assert "@sec:intro" in soup.get_text()


def test_latex_output_renders_ref() -> None:
    html = render_markdown(
        "# Interruptions {#sec:interruptions}\n\nVoir @[sec:interruptions] et @tbl:constats.",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html
    latex = LaTeXRenderer().render(html)
    assert "\\label{sec:interruptions}" in latex
    assert "\\ref{sec:interruptions}" in latex
    assert "\\ref{tbl:constats}" in latex
