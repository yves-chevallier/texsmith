import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


try:
    from texsmith.cli import convert  # type: ignore[attr-defined]
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    if exc.name == "typer":
        convert = None  # type: ignore[assignment]
    else:  # pragma: no cover - unexpected failure
        raise


@unittest.skipIf(convert is None, "Typer dependency is not available.")
class CliConvertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.previous_cwd = Path.cwd()
        os.chdir(self.project_root)

    def tearDown(self) -> None:
        os.chdir(self.previous_cwd)

    def test_convert_template_writes_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "sample.html"
            source.write_text("<h1>Titre</h1>", encoding="utf-8")
            output_dir = temp_path / "build"

            assert convert is not None  # for type checkers
            convert(
                input_path=source,
                output_dir=output_dir,
                template="./book",
            )

            output_file = output_dir / "sample.tex"
            self.assertTrue(output_file.exists())
            content = output_file.read_text(encoding="utf-8")
            self.assertIn("\\mainmatter", content)
            self.assertIn("Titre", content)

            class_file = output_dir / "mkbook.cls"
            self.assertTrue(class_file.exists())
            class_content = class_file.read_text(encoding="utf-8")
            self.assertNotIn("\\VAR{", class_content)
            self.assertIn("\\RequirePackage[english]{babel}", class_content)

            circles = output_dir / "covers" / "circles.tex"
            self.assertTrue(circles.exists())
            circles_content = circles.read_text(encoding="utf-8")
            self.assertNotIn("\\VAR{", circles_content)
            self.assertIn("\\def\\covercolor{indigo(dye)}", circles_content)

    def test_convert_template_applies_markdown_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "sample.md"
            source.write_text(
                """---
meta:
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

            assert convert is not None  # for type checkers
            convert(
                input_path=source,
                output_dir=output_dir,
                template="./article",
            )

            output_file = output_dir / "sample.tex"
            self.assertTrue(output_file.exists())
            content = output_file.read_text(encoding="utf-8")
            self.assertIn(r"\title{Sample Article\\\large Insights on Cheese}", content)
            self.assertIn(
                r"\author{Alice Example\thanks{Example University} \and Bob Example}",
                content,
            )
            self.assertIn(r"\date{2024-10-20}", content)
            self.assertIn(r"\usepackage[french]{babel}", content)

    def test_nature_template_applies_table_override(self) -> None:
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

            assert convert is not None  # for type checkers
            convert(
                input_path=source,
                output_dir=output_dir,
                template="./nature",
            )

            output_file = output_dir / "sample.tex"
            self.assertTrue(output_file.exists())
            content = output_file.read_text(encoding="utf-8")
            self.assertIn(r"\begin{tabular}{@{}ll@{}}", content)
            self.assertIn(r"\caption{Overview}\label{tbl-sample}%", content)
            self.assertIn(r"\botrule", content)
            self.assertNotIn(r"\textbf{Col 1}", content)


if __name__ == "__main__":
    unittest.main()
