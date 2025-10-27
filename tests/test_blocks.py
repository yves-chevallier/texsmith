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
    assert "\\begin{tabular}" in latex
    assert latex.index("\\begin{displayquote}") < latex.index("\\begin{tabular}")


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
    assert "\\item[Apple] Sweet" in latex
    assert "\\item[Banana] Yellow" in latex


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


def test_horizontal_rule_removed(renderer: LaTeXRenderer) -> None:
    html = "<p>Before</p><hr /><p>After</p>"
    latex = renderer.render(html)
    assert "Before" in latex
    assert "After" in latex
    assert "\\rule{\\textwidth}{0.4pt}" in latex


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


def test_arithmatex_block_preserved(renderer: LaTeXRenderer) -> None:
    html = '<div class="arithmatex">$$\nE = mc^2\n$$</div>'
    latex = renderer.render(html)
    assert "$$\nE = mc^2\n$$" in latex


def test_hidden_latex_block(renderer: LaTeXRenderer) -> None:
    html = '<p class="latex-raw" style="display:none;">\\newline\\textbf{hidden}</p>'
    latex = renderer.render(html)
    assert "\\newline\\textbf{hidden}" in latex
