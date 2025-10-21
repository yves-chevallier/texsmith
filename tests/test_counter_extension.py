from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for candidate in (PROJECT_ROOT, SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from counter import COUNTER_KEY, build_renderer
from mkdocs_latex import DocumentState


def test_counter_extension_renders_incremented_markers() -> None:
    renderer = build_renderer()
    state = DocumentState()

    html = '<p><span class="data-counter"></span> <span class="data-counter"></span></p>'
    latex = renderer.render(html, state=state)

    assert "\\counter{1}" in latex
    assert "\\counter{2}" in latex
    assert latex.count("\\counter{") == 2
    assert state.peek_counter(COUNTER_KEY) == 2
