import logging
from pathlib import Path
from types import SimpleNamespace

from mkdocs_plugin_texsmith.plugin import LatexPlugin, log
from mkdocs_plugin_texsmith.site import SiteIndex
import pytest

from texsmith.diagnostics import LoggingEmitter


def test_lowering_reports_a_diagnostic_with_the_page_path(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """A page's diagnostics are logged as ``path:line:col: severity code: message``."""
    page_path = tmp_path / "docs" / "intro.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text("# Intro\n\nSee @fw:nothing.\n", encoding="utf-8")

    site = SiteIndex(project_dir=tmp_path, emitter=LoggingEmitter(logger_obj=log))
    page = SimpleNamespace(
        file=SimpleNamespace(src_uri="docs/intro.md", abs_src_path=str(page_path))
    )

    with caplog.at_level(logging.WARNING):
        lowered = site.lower(page, page_path.read_text(encoding="utf-8"))
        assert lowered is not None
        site.report(lowered)

    messages = [record.getMessage() for record in caplog.records]
    assert messages, "Expected the plugin to log the page's diagnostics"
    # The page path, not the temporary absolute one, and tmark's code.
    assert any("docs/intro.md:3:6: warning ref-unresolved:" in message for message in messages)


def test_every_page_of_a_build_registers_in_one_table(tmp_path: Path) -> None:
    """Two pages of a site take two file ids, so their spans do not collide.

    Each page used to lower against a table of its own and take id 0 in it,
    which made the ``(code, span, message)`` identity of a finding on page two
    equal to the same finding on page one.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    site = SiteIndex(project_dir=tmp_path, emitter=LoggingEmitter(logger_obj=log))

    spans: list[int] = []
    for name in ("first.md", "second.md"):
        path = docs / name
        path.write_text(f"# {name}\n\nSee @fw:nothing.\n", encoding="utf-8")
        page = SimpleNamespace(file=SimpleNamespace(src_uri=f"docs/{name}", abs_src_path=str(path)))
        lowered = site.lower(page, path.read_text(encoding="utf-8"))
        assert lowered is not None
        spans.extend(
            record.span.file for record in lowered.diagnostics if record.code == "ref-unresolved"
        )

    assert spans == [0, 1]
    files = site.emitter.sink.files
    # ``files.path()`` holds the page's ``src_uri`` as a ``PurePosixPath``:
    # ``.as_posix()`` is the stable comparison, ``str()`` would be OS-native.
    assert [files.path(index).as_posix() for index in spans] == ["docs/first.md", "docs/second.md"]


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
