import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig
from texsmith.core.context import DocumentState


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_strong_tag_converted(renderer: LaTeXRenderer) -> None:
    html = "<strong>Important</strong>"
    latex = renderer.render(html)
    assert latex.strip() == "\\textbf{Important}"


def test_emphasis_tag_converted(renderer: LaTeXRenderer) -> None:
    html = "<em>Italic</em>"
    latex = renderer.render(html)
    assert latex.strip() == "\\emph{Italic}"


def test_strikethrough_tag_converted(renderer: LaTeXRenderer) -> None:
    html = "<del>Removed</del>"
    latex = renderer.render(html)
    assert latex.strip() == "\\sout{Removed}"


def test_underline_tag_converted(renderer: LaTeXRenderer) -> None:
    html = "<ins>Highlight</ins>"
    latex = renderer.render(html)
    assert latex.strip() == "\\uline{Highlight}"


def test_critic_substitution(renderer: LaTeXRenderer) -> None:
    html = "<p><span class='critic subst'><del>bad</del><ins>good</ins></span></p>"
    latex = renderer.render(html)
    assert "\\xout{bad}\\ \\uline{good}" in latex


def test_nested_strong_inside_emphasis(renderer: LaTeXRenderer) -> None:
    html = "<p><em>Very <strong>important</strong></em></p>"
    latex = renderer.render(html)
    assert "\\emph{Very \\textbf{important}}" in latex


def test_nested_emphasis_inside_underline(renderer: LaTeXRenderer) -> None:
    html = "<p><ins><em>note</em></ins></p>"
    latex = renderer.render(html)
    assert "\\uline{\\emph{note}}" in latex


def test_keyboard_shortcut_rendering(renderer: LaTeXRenderer) -> None:
    html = "<p>Press <span class='keys'><kbd class='key-control'>Ctrl</kbd><kbd>s</kbd></span></p>"
    latex = renderer.render(html)
    assert "\\keystroke{Ctrl}+\\keystroke{S}" in latex


def test_mark_tag_converted(renderer: LaTeXRenderer) -> None:
    html = "<p><mark>Important</mark></p>"
    latex = renderer.render(html)
    assert "\\texsmithHighlight{Important}" in latex


def test_latex_text_span_converted(renderer: LaTeXRenderer) -> None:
    html = "<p><span class='latex-text'>LaTeX</span></p>"
    latex = renderer.render(html)
    assert "\\LaTeX{}" in latex


def test_inline_highlight_code(renderer: LaTeXRenderer) -> None:
    html = (
        "<p>Say <code class='highlight'><span class='nb'>print</span>"
        "<span class='p'>(</span><span class='s2'>\"Hi\"</span>"
        "<span class='p'>)</span></code></p>"
    )
    latex = renderer.render(html)
    assert r"\ttfamily" in latex and "PYZ" in latex


def test_unicode_superscript_conversion(renderer: LaTeXRenderer) -> None:
    html = "<p>(0.1 s⁻¹, 1 s⁻¹, 10 s⁻¹)</p>"
    latex = renderer.render(html)
    assert (
        "(0.1 s\\textsuperscript{-1}, 1 s\\textsuperscript{-1}, 10 s\\textsuperscript{-1})" in latex
    )


def test_unicode_subscript_conversion(renderer: LaTeXRenderer) -> None:
    html = "<p>H₂O and CO₂</p>"
    latex = renderer.render(html)
    assert "H\\textsubscript{2}O" in latex
    assert "CO\\textsubscript{2}" in latex


def test_subscript_tag_converted(renderer: LaTeXRenderer) -> None:
    html = "<p>H<sub>2</sub>O</p>"
    latex = renderer.render(html)
    assert "H\\textsubscript{2}O" in latex


def test_superscript_tag_converted(renderer: LaTeXRenderer) -> None:
    html = "<p>x<sup>2</sup></p>"
    latex = renderer.render(html)
    assert "x\\textsuperscript{2}" in latex


def test_abbreviation_renders_acronym(renderer: LaTeXRenderer) -> None:
    html = '<p><abbr title="Hypertext Transfer Protocol">HTTP</abbr></p>'
    latex = renderer.render(html)
    assert "\\acrshort{HTTP}" in latex


def test_abbreviation_missing_title_falls_back_to_text(renderer: LaTeXRenderer) -> None:
    html = "<p><abbr>HTTP</abbr></p>"
    latex = renderer.render(html)
    assert "HTTP" in latex
    assert "\\acrshort" not in latex


def test_abbreviation_conflicting_definitions_warn(renderer: LaTeXRenderer) -> None:
    html = (
        "<p><abbr title='Hypertext Transfer Protocol'>HTTP</abbr>"
        " <abbr title='Different'>HTTP</abbr></p>"
    )
    with pytest.warns(UserWarning, match="Inconsistent acronym definition"):
        renderer.render(html)


def test_index_span_with_bold_style(renderer: LaTeXRenderer) -> None:
    html = '<p><span data-tag-name="term" data-tag-style="b">Term</span></p>'
    latex = renderer.render(html)
    assert "Term\\index{\\textbf{term}}" in latex


def test_index_span_without_style(renderer: LaTeXRenderer) -> None:
    html = '<p><span data-tag-name="Entry">Label</span></p>'
    latex = renderer.render(html)
    assert "Label\\index{Entry}" in latex


def test_index_span_with_italic_style(renderer: LaTeXRenderer) -> None:
    html = '<p><span data-tag-name="horse" data-tag-style="i">Horse</span></p>'
    latex = renderer.render(html)
    assert "Horse\\index{\\textit{horse}}" in latex


def test_index_anchor_with_bold_italic_style(renderer: LaTeXRenderer) -> None:
    html = '<p><a href="#" data-tag-name="complex" data-tag-style="bi"></a></p>'
    latex = renderer.render(html)
    assert "\\index{\\textbf{\\textit{complex}}}" in latex


def test_index_nested_entries(renderer: LaTeXRenderer) -> None:
    html = '<p><span data-tag-name="first, second ,third">Nested</span></p>'
    latex = renderer.render(html)
    assert "Nested\\index{first!second!third}" in latex


def test_document_state_tracks_index_and_acronyms(renderer: LaTeXRenderer) -> None:
    state = DocumentState()
    html = (
        "<p><span data-tag-name='term'>word</span> "
        "<abbr title='Hypertext Transfer Protocol'>HTTP</abbr></p>"
    )
    renderer.render(html, state=state)
    assert state.has_index_entries is True
    assert "HTTP" in state.acronym_keys
    key = state.acronym_keys["HTTP"]
    assert key in state.acronyms
    assert state.acronyms[key] == ("HTTP", "Hypertext Transfer Protocol")


def test_arithmatex_inline_preserved(renderer: LaTeXRenderer) -> None:
    html = "<p>Inline math <span class='arithmatex'>\\(E = mc^2\\)</span></p>"
    latex = renderer.render(html)
    assert "Inline math \\(E = mc^2\\)" in latex
