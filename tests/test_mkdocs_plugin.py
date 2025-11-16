from pathlib import Path
import warnings

from mkdocs_plugin_texsmith.plugin import LatexPlugin, NavEntry, log
import pytest


def test_plugin_logs_render_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plugin = LatexPlugin()
    plugin._project_dir = tmp_path

    entry = NavEntry(
        title="Intro",
        level=1,
        numbered=True,
        drop_title=False,
        part="mainmatter",
        is_page=True,
        src_path="docs/intro.md",
        abs_src_path=tmp_path / "docs/intro.md",
    )

    recorded: list[str] = []

    def capture(message: str, *args: object) -> None:
        recorded.append(message % args if args else message)

    monkeypatch.setattr(log, "warning", capture)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        warnings.warn("Footnote issue", UserWarning, stacklevel=2)

    warning_msg = captured[0]
    warning_msg.filename = str(tmp_path / "docs" / "intro.py")
    warning_msg.lineno = 42

    plugin._log_render_warning(entry, warning_msg)

    assert recorded, "Expected the plugin to log the captured warning"
    message = recorded[0]
    assert "TeXSmith warning on page 'Intro'" in message
    assert "Footnote issue" in message
    assert "docs/intro.py:42" in message


def test_plugin_announces_latexmk_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plugin = LatexPlugin()
    plugin._project_dir = tmp_path

    output_root = tmp_path / "press" / "book"
    tex_path = output_root / "texsmith-docs.tex"

    recorded: list[str] = []

    def capture(message: str, *args: object) -> None:
        recorded.append(message % args if args else message)

    monkeypatch.setattr(log, "info", capture)

    plugin._announce_latexmk_command(output_root, tex_path)

    assert recorded, "Expected latexmk hint to be logged"
    message = recorded[-1]
    assert "Press bundle ready" in message
    assert "latexmk -cd" in message
    assert "press/book/texsmith-docs.tex" in message
