from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


try:
    from texsmith.ui.cli import render  # type: ignore[attr-defined]
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    if exc.name == "typer":
        render = None  # type: ignore[assignment]
    else:  # pragma: no cover - unexpected failure
        raise


pytestmark = pytest.mark.skipif(render is None, reason="Typer dependency is not available.")


def _template_path(name: str) -> str:
    project_root = Path(__file__).resolve().parents[1]
    candidate = project_root / "templates" / name
    if candidate.exists():
        return str(candidate)

    builtin = project_root / "src" / "texsmith" / "templates" / name
    if builtin.exists():
        return str(builtin)

    raise AssertionError(f"Template '{name}' is unavailable")


@pytest.fixture(autouse=True)
def _change_to_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(project_root)


def test_render_template_writes_file() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source = temp_path / "sample.html"
        source.write_text("<h1>Titre</h1>", encoding="utf-8")
        output_dir = temp_path / "build"

        assert render is not None  # for type checkers
        render(
            input_path=source,
            output=output_dir,
            template=_template_path("book"),
        )

        output_file = output_dir / "sample.tex"
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "\\mainmatter" in content
        assert "Titre" in content
        assert "\\usepackage[english]{babel}" in content

        latexmkrc = output_dir / ".latexmkrc"
        assert latexmkrc.exists()
        rc_content = latexmkrc.read_text(encoding="utf-8")
        assert "\\VAR{" not in rc_content
        assert "$lualatex" in rc_content

        assert not (output_dir / "covers").exists()
        assert not (output_dir / "titlepage.tex").exists()


def test_render_template_applies_markdown_metadata() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source = temp_path / "sample.md"
        source.write_text(
            """---
press:
  title: Sample Article
  subtitle: Insights on Cheese
  authors:
    - name: Alice Example
      affiliation: Example University
    - name: Bob Example
  date: 2024-10-20
  language: fr
---

# Introduction

Content here.
""",
            encoding="utf-8",
        )
        output_dir = temp_path / "build"

        assert render is not None  # for type checkers
        render(
            input_path=source,
            output=output_dir,
            template=_template_path("article"),
        )

        output_file = output_dir / "sample.tex"
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert r"\title{Sample Article\\\large Insights on Cheese}" in content
        assert r"\author{Alice Example\thanks{Example University} \and Bob Example}" in content
        assert r"\date{2024-10-20}" in content
        assert r"\usepackage[french]{babel}" in content


def test_render_multi_document_from_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensure relative inputs work for multi-document rendering."""
    monkeypatch.chdir(tmp_path)
    for name, title in (("a.md", "Zeus"), ("b.md", "Hera"), ("c.md", "Poseidon")):
        (tmp_path / name).write_text(f"# {title}\n\nHello.", encoding="utf-8")
    (tmp_path / "config.yml").write_text("press:\n  title: Sample\n", encoding="utf-8")

    output_dir = tmp_path / "build"

    assert render is not None  # for type checkers
    render(
        inputs=[
            Path("a.md"),
            Path("b.md"),
            Path("c.md"),
            Path("config.yml"),
        ],
        output=output_dir,
        template=_template_path("article"),
    )

    main_tex = output_dir / "main.tex"
    assert main_tex.exists()
    fragment_a = output_dir / "a.tex"
    assert fragment_a.exists()
    content = fragment_a.read_text(encoding="utf-8")
    assert "\\section{Zeus}" in content
    assert "\\subsection{Zeus}" not in content
