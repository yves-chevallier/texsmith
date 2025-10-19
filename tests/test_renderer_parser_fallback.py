import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from latex.renderer import LaTeXRenderer


def test_renderer_falls_back_to_builtin_parser() -> None:
    renderer = LaTeXRenderer(parser="nonexistent-parser")

    latex = renderer.render("<p>Hello</p>")

    assert latex.strip() == "Hello"
