from pathlib import Path

from texsmith.api import Document, TemplateSession
from texsmith.core.templates import load_template_runtime


def _render_with_engine(tmp_path: Path, engine: str | None) -> tuple[str, str, str, object]:
    md = tmp_path / "doc.md"
    md.write_text("```python\nprint('hello')\n```", encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    if engine:
        session.update_options({"code": {"engine": engine}})
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    sty_content = (tmp_path / "build" / "ts-code.sty").read_text(encoding="utf-8")
    latexmkrc = (tmp_path / "build" / ".latexmkrc").read_text(encoding="utf-8")
    return tex_content, sty_content, latexmkrc, result


def test_default_engine_is_pygments(tmp_path: Path) -> None:
    tex, sty, latexmkrc, result = _render_with_engine(tmp_path, None)

    assert "\\PY{" in tex
    assert "minted" not in sty
    assert "\\RequirePackage{listings}" not in sty
    assert "--shell-escape" not in latexmkrc
    assert not result.requires_shell_escape


def test_minted_engine_enables_shell_escape(tmp_path: Path) -> None:
    _, sty, latexmkrc, result = _render_with_engine(tmp_path, "minted")

    assert "\\RequirePackage{minted}" in sty
    assert "--shell-escape" in latexmkrc
    assert result.requires_shell_escape


def test_listings_engine_uses_listings_package(tmp_path: Path) -> None:
    tex, sty, latexmkrc, result = _render_with_engine(tmp_path, "listings")

    assert "\\RequirePackage{listings}" in sty
    assert "\\usemintedstyle" not in sty
    assert "--shell-escape" not in latexmkrc
    assert "\\lstset" in sty
    assert not result.requires_shell_escape
    assert "\\PY{" not in tex
