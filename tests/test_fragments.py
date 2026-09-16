from pathlib import Path

from texsmith.core.documents import Document
from texsmith.core.templates import load_template_runtime
from texsmith.core.templates.session import TemplateSession
from texsmith.diagnostics import LoggingEmitter


def test_fragments_default_injection(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\nBody", encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-fonts}" in tex_content
    assert "\\usepackage{ts-callouts}" not in tex_content
    assert "\\usepackage{ts-keystrokes}" not in tex_content
    assert "\\usepackage{ts-code}" not in tex_content
    assert "\\usepackage{ts-glossary}" not in tex_content
    assert "\\usepackage{ts-index}" not in tex_content
    assert "\\usepackage{ts-todolist}" not in tex_content
    assert "\\usepackage[a4paper]{geometry}" in tex_content
    assert not (tmp_path / "build" / "ts-callouts.sty").exists()
    assert not (tmp_path / "build" / "ts-keystrokes.sty").exists()
    assert not (tmp_path / "build" / "ts-code.sty").exists()
    assert not (tmp_path / "build" / "ts-glossary.sty").exists()
    assert not (tmp_path / "build" / "ts-index.sty").exists()
    assert not (tmp_path / "build" / "ts-todolist.sty").exists()
    assert (tmp_path / "build" / "ts-fonts.sty").exists()


def test_ctan_package_failure_reaches_the_sink_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """The emitter threaded into ``render_fragments``/``FontsConfig`` actually fires.

    ``ts-fonts`` builds its config through ``wrap_template_document``'s
    ``render_fragments`` call, not a pass — a real front-matter value
    (``fonts.family: pagella``, a valid choice) drives it there, then a
    failing CTAN download proves the wiring reaches that far, not just the
    unit-level ``_ensure_ctan_sty`` call.
    """

    def _boom(url: str) -> None:
        raise OSError("network disabled in tests")

    monkeypatch.setattr("texsmith.fonts.provisioning.open_url", _boom)

    md = tmp_path / "doc.md"
    md.write_text("---\nfonts:\n  family: pagella\n---\nBody\n", encoding="utf-8")

    emitter = LoggingEmitter()
    session = TemplateSession(load_template_runtime("article"), emitter=emitter)
    session.add_document(Document.from_markdown(md))
    session.render(tmp_path / "build")

    codes = [d.code for d in emitter.sink]
    assert "font-fallback" in codes


def test_custom_fragment_rendering(tmp_path: Path) -> None:
    fragment = tmp_path / "foo.sty"
    fragment.write_text(
        "\\ProvidesPackage{foo}\\newcommand{\\FooValue}{\\VAR{foo}}\n", encoding="utf-8"
    )

    md = tmp_path / "doc.md"
    md.write_text(
        "---\npress:\n  fragments:\n    - foo.sty\n  foo: 42\n---\nBody\n",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{foo}" in tex_content
    rendered_fragment = (tmp_path / "build" / "foo.sty").read_text(encoding="utf-8")
    assert "42" in rendered_fragment


def test_keystrokes_fragment_renders_when_used(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("Press ++ctrl+s++ to save.", encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-keystrokes}" in tex_content
    assert "\\tskeys{Ctrl,S}" in tex_content
    assert (tmp_path / "build" / "ts-keystrokes.sty").exists()


def test_keystrokes_fragment_accepts_labels_that_are_not_csname_safe(tmp_path: Path) -> None:
    """``++alt+left++`` and friends reach ``\\tskeys`` as math, not as a csname.

    The writer resolves an arrow key to ``\\(\\leftarrow\\)``; feeding that to
    ``\\csname ts@key@...`` used to abort the LaTeX run with
    ``Missing \\endcsname inserted``, so the fragment looks the key-label table
    up on the *string* form of the label and prints the label unchanged when it
    is not a registered name.
    """

    md = tmp_path / "doc.md"
    md.write_text("Press ++alt+left++, ++ctrl+s++ and ++shift+←++.", encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\tskeys{Ctrl,S}" in tex_content
    assert "\\(\\leftarrow\\)" in tex_content

    fragment = (tmp_path / "build" / "ts-keystrokes.sty").read_text(encoding="utf-8")
    assert "\\exp_args:Nx \\__ts_key_typeset:nn { \\tl_to_str:n {#1} } {#1}" in fragment


def test_todolist_fragment_renders_when_used(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("- [x] Task\n- [ ] Other task\n", encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-todolist}" in tex_content
    assert "\\begin{tstasklist}" in tex_content
    assert (tmp_path / "build" / "ts-todolist.sty").exists()


def test_callouts_fragment_renders_when_used(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text(
        "!!! info\n    Important callout content.\n",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-callouts}" in tex_content
    assert (tmp_path / "build" / "ts-callouts.sty").exists()
