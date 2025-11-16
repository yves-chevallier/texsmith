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

    builtin = project_root / "src" / "texsmith" / "builtin_templates" / name
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

        class_file = output_dir / "mkbook.cls"
        assert class_file.exists()
        class_content = class_file.read_text(encoding="utf-8")
        assert "\\VAR{" not in class_content
        assert "\\RequirePackage[english]{babel}" in class_content

        circles = output_dir / "covers" / "circles.tex"
        assert circles.exists()
        circles_content = circles.read_text(encoding="utf-8")
        assert "\\VAR{" not in circles_content
        assert "\\def\\covercolor{indigo(dye)}" in circles_content


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


def test_nature_template_applies_table_override() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source = temp_path / "sample.html"
        source.write_text(
            """<table id="tbl-sample">
<caption>Overview</caption>
<tr><th>Col 1</th><th>Col 2</th></tr>
<tr><td>Foo</td><td>Bar</td></tr>
</table>""",
            encoding="utf-8",
        )
        output_dir = temp_path / "build"

        assert render is not None  # for type checkers
        render(
            input_path=source,
            output=output_dir,
            template=_template_path("nature"),
        )

        output_file = output_dir / "sample.tex"
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert r"\begin{tabular}{@{}ll@{}}" in content
        assert r"\caption{Overview}\label{tbl-sample}" in content
        assert r"\botrule" in content
        assert r"\textbf{Col 1}" not in content
