from pathlib import Path

from texsmith.api import Document, TemplateSession
from texsmith.core.templates import load_template_runtime


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
    md.write_text("Press \\keystroke{Ctrl}+\\keystroke{S}", encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-keystrokes}" in tex_content
    assert (tmp_path / "build" / "ts-keystrokes.sty").exists()


def test_todolist_fragment_renders_when_used(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text(
        "\\begin{todolist}\n\\item\\done Task\n\\end{todolist}",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\usepackage{ts-todolist}" in tex_content
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
