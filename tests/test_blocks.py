import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.core.config import BookConfig


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_inline_code_rendering(renderer: LaTeXRenderer) -> None:
    html = "<p>Use <code>print('hi')</code> in Python.</p>"
    latex = renderer.render(html)
    assert "\\texttt{print('hi')}" in latex


def test_blockquote_rendering(renderer: LaTeXRenderer) -> None:
    html = "<blockquote><p>Quoted wisdom.</p></blockquote>"
    latex = renderer.render(html)
    assert "\\begin{displayquote}" in latex
    assert "Quoted wisdom." in latex
    assert "\\end{displayquote}" in latex


def test_blockquote_with_nested_table(renderer: LaTeXRenderer) -> None:
    html = """
    <blockquote>
        <table>
            <tr>
                <th>Col1</th>
                <th>Col2</th>
            </tr>
            <tr>
                <td>Val1</td>
                <td>Val2</td>
            </tr>
        </table>
    </blockquote>
    """
    latex = renderer.render(html)
    assert "\\begin{displayquote}" in latex
    assert "\\begin{center}" in latex
    assert "\\begin{tabularx}" in latex
    assert latex.index("\\begin{displayquote}") < latex.index("\\begin{tabularx}")


def test_ordered_list_rendering(renderer: LaTeXRenderer) -> None:
    html = "<ol><li>First</li><li>Second</li></ol>"
    latex = renderer.render(html)
    assert "\\begin{enumerate}" in latex
    assert "\\item First" in latex
    assert "\\item Second" in latex


def test_unordered_list_with_formatting(renderer: LaTeXRenderer) -> None:
    html = "<ul><li>Item <em>one</em></li><li><strong>Two</strong></li></ul>"
    latex = renderer.render(html)
    assert "\\begin{itemize}" in latex
    assert "Item \\emph{one}" in latex
    assert "\\textbf{Two}" in latex


def test_task_list_rendering(renderer: LaTeXRenderer) -> None:
    html = "<ul><li>[x] Completed task</li><li>[ ] Pending task</li></ul>"
    latex = renderer.render(html)
    assert "\\begin{todolist}" in latex
    assert "\\done" in latex
    assert "Completed task" in latex
    assert "Pending task" in latex


def test_definition_list_rendering(renderer: LaTeXRenderer) -> None:
    html = "<dl><dt>Apple</dt><dd>Sweet</dd><dt>Banana</dt><dd>Yellow</dd></dl>"
    latex = renderer.render(html)
    assert "\\begin{description}" in latex
    assert "\\item[{ Apple }] Sweet" in latex
    assert "\\item[{ Banana }] Yellow" in latex


def test_description_list_preserves_code(renderer: LaTeXRenderer) -> None:
    html = """
    <dl>
        <dt><code>DoiBibliographyFetcher</code> encapsulates remote lookups.</dt>
        <dd><code>bibliography_data_from_string</code> converts to <code>BibliographyData</code>.</dd>
    </dl>
    """
    latex = renderer.render(html)
    assert "\\item[{ \\texttt{DoiBibliographyFetcher} encapsulates remote lookups. }]" in latex
    assert "\\texttt{bibliography\\_data\\_from\\_string}" in latex
    assert "\\texttt{BibliographyData}" in latex


def test_highlight_block_nested_in_doc_container(renderer: LaTeXRenderer) -> None:
    html = """
    <div class="doc doc-contents first">
        <div class="highlight">
            <pre><span></span><code><span class="gp">&gt;&gt;&gt; </span>print("hi")</code></pre>
        </div>
    </div>
    """
    latex = renderer.render(html)
    assert "\\begin{code}" in latex
    assert "print(\\PYZdq{}hi\\PYZdq{})" in latex or "PYZgt" in latex


def test_inline_code_in_doc_container(renderer: LaTeXRenderer) -> None:
    html = """
    <div class="doc doc-contents first">
        <p>This module uses <code>@renders</code> macros.</p>
        <p>:class:<code>_DOMVisitor</code> to apply handlers.</p>
    </div>
    """
    latex = renderer.render(html)
    assert "\\texttt{@renders}" in latex
    assert "\\texttt{\\_DOMVisitor}" in latex


def test_empty_description_list_dropped(renderer: LaTeXRenderer) -> None:
    html = "<dl><dt></dt><dd></dd></dl>"
    with pytest.warns(UserWarning, match="Discarding empty description list"):
        latex = renderer.render(html)
    assert "\\begin{description}" not in latex


def test_footnote_conversion(renderer: LaTeXRenderer) -> None:
    html = """
    <p>See note<sup id="fnref:1"><a href="#fn:1">1</a></sup>.</p>
    <div class="footnote">
        <ol>
            <li id="fn:1">Footnote content</li>
        </ol>
    </div>
    """
    latex = renderer.render(html)
    assert "\\footnote{Footnote content}" in latex
    assert "<div" not in latex


def test_multiline_footnote_removed(renderer: LaTeXRenderer) -> None:
    html = """
    <p>See note<sup id="fnref:1"><a href="#fn:1">1</a></sup>.</p>
    <div class="footnote">
        <ol>
            <li id="fn:1">
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
            </li>
        </ol>
    </div>
    """
    with pytest.warns(UserWarning, match="Footnote '1' spans multiple lines"):
        latex = renderer.render(html)
    assert "\\footnote" not in latex


def test_horizontal_rule_removed(renderer: LaTeXRenderer) -> None:
    html = "<p>Before</p><hr /><p>After</p>"
    latex = renderer.render(html)
    assert "Before" in latex
    assert "After" in latex
    assert "\\rule{\\linewidth}{0.4pt}" in latex


def test_tabbed_content_rendering(renderer: LaTeXRenderer) -> None:
    html = """
    <div class="tabbed-set">
        <div class="tabbed-labels">
            <label>Python</label>
            <label>JavaScript</label>
        </div>
        <input type="radio" />
        <div class="tabbed-content">
            <div class="tabbed-block">
                <p>Hello from Python.</p>
            </div>
            <div class="tabbed-block">
                <p>Hello from JS.</p>
            </div>
        </div>
    </div>
    """
    latex = renderer.render(html)
    assert "\\textbf{Python}\\par" in latex
    assert "\\textbf{JavaScript}\\par" in latex
    assert "Hello from Python." in latex
    assert "Hello from JS." in latex


def test_tabbed_code_blocks_preserved(renderer: LaTeXRenderer) -> None:
    html = """
    <div class="tabbed-set">
        <div class="tabbed-labels">
            <label>CLI</label>
            <label>Python</label>
        </div>
        <input type="radio" />
        <div class="tabbed-content">
            <div class="tabbed-block">
                <div class="language-bash highlight">
                    <pre><span></span><code>uv tool install texsmith</code></pre>
                </div>
            </div>
            <div class="tabbed-block">
                <div class="language-python highlight">
                    <pre><span></span><code>print("hello")</code></pre>
                </div>
            </div>
        </div>
    </div>
    """
    latex = renderer.render(html)
    assert "\\textbf{CLI}\\par" in latex
    assert "\\textbf{Python}\\par" in latex
    assert "\\begin{code}{bash}" in latex
    assert "\\begin{code}{python}" in latex


def test_admonition_preserves_formatting(renderer: LaTeXRenderer) -> None:
    html = """
    <div class="admonition seealso">
        <p class="admonition-title">Links</p>
        <p>Use <code>foo_bar</code> inside callouts.</p>
        <div class="language-python highlight">
            <pre><span></span><code>print("hello")</code></pre>
        </div>
        <ul>
            <li>Bullet <strong>item</strong></li>
        </ul>
    </div>
    """
    latex = renderer.render(html)
    assert "\\begin{callout}[callout info]" in latex
    assert "\\texttt{foo\\_bar}" in latex
    assert "\\begin{code}{python}" in latex
    assert "\\begin{itemize}" in latex


def test_blockquote_callout_transformed(renderer: LaTeXRenderer) -> None:
    html = """
    <blockquote>
        <p>[!seealso] Cross-links</p>
        <p>Check <code>uv tool install texsmith</code>.</p>
    </blockquote>
    """
    latex = renderer.render(html)
    assert "\\begin{callout}[callout info]" in latex
    assert "\\texttt{uv tool install texsmith}" in latex


def test_code_block_with_paragraph_keyword_not_mermaid(renderer: LaTeXRenderer) -> None:
    html = """
    <div class="highlight">
        <pre><span></span><code>
Paragraph headings explain paragraphs.

This is a paragraph with a trailing space.
        </code></pre>
    </div>
    """
    latex = renderer.render(html)
    assert "\\begin{code}{text}" in latex
    assert "Paragraph headings explain paragraphs." in latex


def test_arithmatex_block_preserved(renderer: LaTeXRenderer) -> None:
    html = '<div class="arithmatex">$$\nE = mc^2\n$$</div>'
    latex = renderer.render(html)
    assert "$$\nE = mc^2\n$$" in latex


def test_arithmatex_block_align_unwrapped(renderer: LaTeXRenderer) -> None:
    html = '<div class="arithmatex">\\[\n\\begin{align*}\nE &= mc^2\n\\end{align*}\n\\]</div>'
    latex = renderer.render(html)
    assert "\\begin{align*}" in latex
    assert "\\[" not in latex


def test_hidden_latex_block(renderer: LaTeXRenderer) -> None:
    html = '<p class="latex-raw" style="display:none;">\\newline\\textbf{hidden}</p>'
    latex = renderer.render(html)
    assert "\\newline\\textbf{hidden}" in latex


def test_hidden_latex_inline_span(renderer: LaTeXRenderer) -> None:
    html = '<span class="latex-raw" style="display:none;">\\clearpage</span>'
    latex = renderer.render(html)
    assert "\\clearpage" in latex
