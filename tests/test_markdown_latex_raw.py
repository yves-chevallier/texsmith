import markdown

from texsmith.ui.cli import DEFAULT_MARKDOWN_EXTENSIONS


def test_latex_raw_fence_converts_to_hidden_paragraph() -> None:
    md = markdown.Markdown(extensions=DEFAULT_MARKDOWN_EXTENSIONS)
    html = md.convert("Intro\n\n/// latex\n\\newline\\textbf{hidden}\n///\n\nOutro")

    assert '<p class="latex-raw" style="display:none;">\\newline\\textbf{hidden}</p>' in html
    assert "<p>Intro</p>" in html
    assert "<p>Outro</p>" in html


def test_latex_raw_without_closing_fence_is_preserved() -> None:
    source = "/// latex\n\\alpha"
    md = markdown.Markdown(extensions=DEFAULT_MARKDOWN_EXTENSIONS)
    html = md.convert(source)

    assert "latex-raw" not in html
    assert "/// latex" in html


def test_inline_latex_shortcut_converts_to_hidden_span() -> None:
    md = markdown.Markdown(extensions=DEFAULT_MARKDOWN_EXTENSIONS)
    html = md.convert("Paragraph {latex}[\\clearpage] text")

    assert '<span class="latex-raw" style="display:none;">\\clearpage</span>' in html
