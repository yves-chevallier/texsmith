"""The fix-ups :mod:`texsmith.site.html` applies to a rendered page.

Both site integrations call these functions over the HTML Python-Markdown
produced, so the round trips below are written in that HTML rather than in
the Markdown behind it.
"""

from __future__ import annotations

import pytest

from texsmith.site.html import NNBSP, french_typography, unescape_table_pipes


def test_a_code_span_in_a_cell_gets_its_pipe_back() -> None:
    html = "<table><tr><td><code>a \\| b</code></td></tr></table>"

    assert unescape_table_pipes(html) == "<table><tr><td><code>a | b</code></td></tr></table>"


def test_a_code_span_outside_a_cell_keeps_its_backslash() -> None:
    html = "<p><code>a \\| b</code></p>"

    assert unescape_table_pipes(html) == html


@pytest.mark.parametrize("mark", [";", ":", "!", "?"])
def test_a_double_punctuation_mark_gains_a_narrow_no_break_space(mark: str) -> None:
    assert french_typography(f"<p>Oui {mark}</p>") == f"<p>Oui{NNBSP}{mark}</p>"
    assert french_typography(f"<p>Oui{mark}</p>") == f"<p>Oui{NNBSP}{mark}</p>"


def test_straight_quotes_become_guillemets() -> None:
    html = '<p>Il a dit &quot;bonjour&quot; puis "au revoir".</p>'

    spaced = french_typography(html)

    # The entity is opaque: only the straight quotes the renderer left are
    # turned into guillemets.
    assert f"«{NNBSP}au revoir{NNBSP}»" in spaced
    assert "&quot;bonjour&quot;" in spaced


def test_the_rules_apply_inside_a_quotation() -> None:
    assert french_typography('<p>"Vraiment?"</p>') == f"<p>«{NNBSP}Vraiment{NNBSP}?{NNBSP}»</p>"


@pytest.mark.parametrize(
    "html",
    [
        "<pre><code>if (a) { b(); }</code></pre>",
        "<p><code>time : 12</code></p>",
        "<script>var a = {x: 1};</script>",
        "<style>a { color : red }</style>",
        '<p><a href="https://x/y?a=1" title="Oui : non" class="md-nav">x</a></p>',
        "<p>d&eacute;j&agrave; et &#233;t&#xe9;</p>",
        "<!-- a comment : here -->",
    ],
)
def test_what_the_rules_never_touch(html: str) -> None:
    assert french_typography(html) == html


def test_a_token_that_only_looks_like_punctuation_is_left_alone() -> None:
    html = "<p>Le train de 12:30 sur http://exemple.fr/a?b=1 arrive.</p>"

    assert french_typography(html) == html


def test_a_space_the_page_already_carries_is_kept_as_it_is() -> None:
    html = f"<p>Oui&nbsp;? Non{NNBSP}! Peut-\u00eatre\u00a0;</p>"

    assert french_typography(html) == html


def test_the_rules_are_idempotent() -> None:
    once = french_typography('<p>Attention : "un test" ; vraiment ?</p>')

    assert french_typography(once) == once


def test_the_text_around_an_inline_tag_is_spaced() -> None:
    html = "<p>Voir <strong>le tableau</strong> : il est <em>long</em> !</p>"

    assert french_typography(html) == (
        f"<p>Voir <strong>le tableau</strong>{NNBSP}: il est <em>long</em>{NNBSP}!</p>"
    )


def test_a_mark_that_follows_a_closing_tag_is_spaced_too() -> None:
    html = "<p><strong>Note</strong> : voir <em>plus loin</em>.</p>"

    assert french_typography(html) == (
        f"<p><strong>Note</strong>{NNBSP}: voir <em>plus loin</em>.</p>"
    )


def test_a_mark_that_opens_a_paragraph_is_left_alone() -> None:
    html = "<p>: un deux-points litt\u00e9ral</p>"

    assert french_typography(html) == html
