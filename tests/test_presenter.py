from types import SimpleNamespace

import pytest
from rich.text import Text

from texsmith.ui.cli import presenter
from texsmith.ui.cli.state import CLIState


def test_render_summary_colors_locations(monkeypatch: pytest.MonkeyPatch) -> None:
    state = CLIState()
    rendered: list[object] = []

    console = SimpleNamespace(is_terminal=True, print=lambda obj: rendered.append(obj))

    class DummyTable:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.rows: list[tuple[object, ...]] = []
            self.columns: list[tuple[tuple[object, ...], dict[str, object]]] = []
            self.title = kwargs.get("title")

        def add_column(self, *args: object, **kwargs: object) -> None:
            self.columns.append((args, kwargs))

        def add_row(self, *cells: object) -> None:
            self.rows.append(cells)

    class DummyBox:
        SQUARE = object()

    monkeypatch.setattr(presenter, "_get_console", lambda _state, *, _stderr=False: console)
    monkeypatch.setattr(presenter, "_rich_components", lambda: (DummyBox, object, DummyTable, Text))

    presenter._render_summary(
        state,
        "",
        [
            ("Main document", "demo.tex", ""),
            ("PDF", "demo.pdf", ""),
            ("Asset", "assets/demo.png", ""),
        ],
    )

    assert rendered, "Table was not rendered"
    table = rendered[0]
    tex_style = table.rows[0][1].style
    pdf_style = table.rows[1][1].style
    asset_style = table.rows[2][1].style

    assert tex_style == "bright_cyan"
    assert pdf_style == "bright_green"
    assert asset_style == "magenta"
