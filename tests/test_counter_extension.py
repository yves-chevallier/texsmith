from pathlib import Path
import sys
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "custom-render"

for candidate in (PROJECT_ROOT, SRC_ROOT, EXAMPLES_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from counter import COUNTER_KEY, HTML, build_renderer  # noqa: E402

from texsmith import DocumentState  # noqa: E402


def test_counter_extension_renders_incremented_markers() -> None:
    renderer = build_renderer()
    state = DocumentState()

    html = '<p><span class="data-counter"></span> <span class="data-counter"></span></p>'
    latex = renderer.render(html, state=state)

    assert "\\counter{1}" in latex
    assert "\\counter{2}" in latex
    assert latex.count("\\counter{") == 2
    assert state.peek_counter(COUNTER_KEY) == 2


def test_counter_example_renders_full_demo_html() -> None:
    renderer = build_renderer()
    state = DocumentState()

    latex = renderer.render(HTML, state=state)
    expected = textwrap.dedent(
        r"""
        \chapter{Counter Example}\label{counter-example}

        This is item \counter{1} but we can also have another
        item \counter{2} and even more \counter{3}.
        """
    ).strip()

    assert latex.strip() == expected
    assert latex.endswith("\n")
    assert state.peek_counter(COUNTER_KEY) == 3


def test_counter_extension_ignores_missing_class() -> None:
    renderer = build_renderer()
    state = DocumentState()

    html = '<p><span class="other"></span> <span></span></p>'
    latex = renderer.render(html, state=state)

    assert "\\counter{" not in latex
    assert state.peek_counter(COUNTER_KEY) == 0
