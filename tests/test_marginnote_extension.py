"""Tests for the ``{margin}[…]`` margin-note extension."""

from __future__ import annotations

import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig
from texsmith.extensions.marginnote import MarginNoteExtension, register_renderer


markdown = pytest.importorskip("markdown")

EXTENSION = MarginNoteExtension()


@pytest.fixture
def renderer() -> LaTeXRenderer:
    renderer = LaTeXRenderer(config=BookConfig(), parser="html.parser")
    register_renderer(renderer)
    return renderer


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------


def test_basic_margin_note_produces_custom_tag() -> None:
    html = markdown.markdown(
        "Avant {margin}[note en marge] apres.",
        extensions=[EXTENSION],
    )
    assert "<ts-marginnote>note en marge</ts-marginnote>" in html


@pytest.mark.parametrize(
    ("suffix", "expected_side"),
    [
        ("l", "l"),
        ("i", "l"),  # inner aliases to left
        ("r", "r"),
        ("o", "r"),  # outer aliases to right
    ],
)
def test_side_suffixes_map_to_data_attribute(suffix: str, expected_side: str) -> None:
    html = markdown.markdown(
        f"Hello {{margin}}[note]{{{suffix}}} world.",
        extensions=[EXTENSION],
    )
    assert f'data-side="{expected_side}"' in html


def test_uppercase_side_suffix_is_accepted() -> None:
    html = markdown.markdown(
        "Ref {margin}[note]{L} end.",
        extensions=[EXTENSION],
    )
    assert 'data-side="l"' in html


def test_inline_markdown_inside_note_is_preserved() -> None:
    html = markdown.markdown(
        "Lorem {margin}[note **importante** with `code`] ipsum.",
        extensions=[EXTENSION],
    )
    assert (
        "<ts-marginnote>note <strong>importante</strong> with <code>code</code></ts-marginnote>"
        in html
    )


def test_nested_brackets_in_content_are_kept() -> None:
    html = markdown.markdown(
        "See {margin}[cite[prenote]{key} details] here.",
        extensions=[EXTENSION],
    )
    assert "<ts-marginnote>cite[prenote]" in html


def test_empty_content_is_ignored() -> None:
    html = markdown.markdown(
        "Nothing {margin}[] here.",
        extensions=[EXTENSION],
    )
    assert "ts-marginnote" not in html
    assert "{margin}" in html  # the literal source stays in place


def test_unknown_side_suffix_is_ignored() -> None:
    html = markdown.markdown(
        "Look {margin}[note]{x} here.",
        extensions=[EXTENSION],
    )
    # The ``{x}`` is not recognised as a side suffix, so it stays in the text
    # and the note has no ``data-side`` attribute.
    assert "<ts-marginnote>note</ts-marginnote>" in html
    assert "{x}" in html


def test_two_notes_in_same_paragraph() -> None:
    html = markdown.markdown(
        "A {margin}[first]{l} then {margin}[second]{r} end.",
        extensions=[EXTENSION],
    )
    assert html.count("<ts-marginnote") == 2


# ---------------------------------------------------------------------------
# HTML → LaTeX
# ---------------------------------------------------------------------------


def test_renderer_emits_plain_marginnote(renderer: LaTeXRenderer) -> None:
    latex = renderer.render("<p>Avant <ts-marginnote>hello</ts-marginnote> apres.</p>")
    assert r"\marginnote{hello}" in latex


def test_renderer_wraps_left_side_with_reversemarginpar(renderer: LaTeXRenderer) -> None:
    latex = renderer.render(
        '<p>Before <ts-marginnote data-side="l">left-hand</ts-marginnote> after.</p>'
    )
    assert r"{\reversemarginpar\marginnote{left-hand}}" in latex


def test_renderer_right_side_emits_plain_marginnote(renderer: LaTeXRenderer) -> None:
    latex = renderer.render(
        '<p>Before <ts-marginnote data-side="r">right-hand</ts-marginnote> after.</p>'
    )
    assert r"\marginnote{right-hand}" in latex
    # No ``\reversemarginpar`` should sneak in for the right-hand variant.
    assert r"\reversemarginpar" not in latex


def test_renderer_preserves_rendered_inline_markup(renderer: LaTeXRenderer) -> None:
    latex = renderer.render(
        "<p>Lorem <ts-marginnote>note <strong>strong</strong> end</ts-marginnote> ipsum.</p>"
    )
    assert r"\marginnote{note \textbf{strong} end}" in latex


def test_renderer_drops_empty_note(renderer: LaTeXRenderer) -> None:
    latex = renderer.render("<p>Nothing <ts-marginnote></ts-marginnote> to see.</p>")
    assert "marginnote" not in latex
    assert "Nothing" in latex and "to see" in latex


# ---------------------------------------------------------------------------
# ts-extra auto-loading
# ---------------------------------------------------------------------------


def test_ts_extra_detects_marginnote_command() -> None:
    """``ts-extra`` must ask for the ``marginnote`` package when the command appears."""
    from texsmith.fragments.extra import ExtraConfig

    context = {"text": r"Some body with a \marginnote{hello} call."}
    config = ExtraConfig.from_context(context)
    names = [name for name, _options in config.packages]
    assert "marginnote" in names


def test_ts_extra_template_marginfont_uses_footnotesize_and_sloppy(tmp_path):
    """The ``ts-extra`` preamble configures ``\\marginfont`` defensively.

    Footnote-size keeps notes compact in narrow margins, ``\\sloppy`` plus
    ``\\emergencystretch`` and lowered hyphenation penalties stop long words
    from poking past the margin box edge: TeX prefers a hyphenation or some
    extra inter-word stretch over an overfull line.
    """
    from texsmith.core.templates.base import _build_environment
    from texsmith.fragments.extra import ExtraFragment

    del tmp_path  # template is packaged alongside the fragment

    template_path = ExtraFragment.pieces[0].template_path
    env = _build_environment(template_path.parent)
    template = env.get_template(template_path.name)
    rendered = template.render(ts_extra_packages=[("marginnote", None)])
    assert r"\renewcommand*{\marginfont}{" in rendered
    assert r"\footnotesize" in rendered
    assert r"\sloppy" in rendered
    assert r"\emergencystretch=1em" in rendered
    assert r"\hyphenpenalty=50" in rendered


def test_ts_extra_template_skips_marginfont_without_marginnote() -> None:
    """``\\marginfont`` override only lands when ``marginnote`` is loaded."""
    from texsmith.core.templates.base import _build_environment
    from texsmith.fragments.extra import ExtraFragment

    template_path = ExtraFragment.pieces[0].template_path
    env = _build_environment(template_path.parent)
    template = env.get_template(template_path.name)
    rendered = template.render(ts_extra_packages=[("float", None)])
    assert "marginfont" not in rendered


def test_ts_extra_template_clamps_marginparwidth_when_marginnote_loaded() -> None:
    """The preamble injects an ``\\AtBeginDocument`` clamp on ``\\marginparwidth``.

    The guard keeps ``\\marginnote`` calls inside whatever horizontal space
    the document's geometry actually reserves, so margin notes never bleed
    past the page edge when the right margin is narrower than LaTeX's
    default ``\\marginparwidth`` (~3.9cm). A small extra safety buffer
    (``\\tsmarginparbuf``) is subtracted on top of ``\\marginparsep`` so a
    slightly-too-long internal line still has room before clipping the page.
    """
    from texsmith.core.templates.base import _build_environment
    from texsmith.fragments.extra import ExtraFragment

    template_path = ExtraFragment.pieces[0].template_path
    env = _build_environment(template_path.parent)
    template = env.get_template(template_path.name)
    rendered = template.render(ts_extra_packages=[("marginnote", None)])
    assert r"\AtBeginDocument{%" in rendered
    assert r"\setlength{\marginparwidth}{\tsmarginparavail}" in rendered
    # The clamp must consider both odd (recto) and even (verso) sides so the
    # smaller physical margin constrains the width in twoside layouts.
    assert r"\if@twoside" in rendered
    assert r"\evensidemargin" in rendered
    assert r"\oddsidemargin" in rendered
    # Safety buffer subtracted on both sides.
    assert r"\newlength{\tsmarginparbuf}" in rendered
    assert r"\setlength{\tsmarginparbuf}{6pt}" in rendered
    assert r"-\tsmarginparbuf" in rendered
