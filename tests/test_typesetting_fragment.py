from pathlib import Path

from texsmith.api import Document, TemplateSession
from texsmith.core.templates import load_template_runtime


def test_typesetting_fragment_not_rendered_by_default(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\nBody", encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\RequirePackage{lineno}" not in tex_content
    assert "\\tsTypesettingApplySpacing" not in tex_content


def test_typesetting_article_options(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text(
        """---
press:
  typesetting:
    paragraph:
      indent: false
      spacing: 1cm
    leading: onehalf
    lineno: true
---
Body
""",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("article"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\setlength{\\parindent}{0pt}" in tex_content
    assert "\\setlength{\\parskip}{1cm}" in tex_content
    assert "\\RequirePackage{setspace}" in tex_content
    assert "\\onehalfspacing" in tex_content
    assert "\\RequirePackage{lineno}" in tex_content
    assert "\\AtBeginDocument{\\linenumbers}" in tex_content


def test_typesetting_memoir_branch(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text(
        """---
press:
  typesetting:
    paragraph:
      indent: true
      spacing: 0.5em
    leading: 1.2
---
Body
""",
        encoding="utf-8",
    )

    session = TemplateSession(load_template_runtime("book"))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")

    tex_content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\@afterindenttrue" in tex_content
    assert "\\setlength{\\parskip}{0.5em}" in tex_content
    assert "\\tsTypesettingApplySpacing{1.2}" in tex_content
    assert "\\Spacing{##1}" in tex_content
