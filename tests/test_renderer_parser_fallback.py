from texsmith.adapters.latex import LaTeXRenderer


def test_renderer_falls_back_to_builtin_parser() -> None:
    renderer = LaTeXRenderer(parser="nonexistent-parser")

    latex = renderer.render("<p>Hello</p>")

    assert latex.strip() == "Hello"
