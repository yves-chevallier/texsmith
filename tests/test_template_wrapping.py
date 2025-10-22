import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from texsmith.templates import TemplateError, copy_template_assets, load_template


class TemplateWrappingTests(unittest.TestCase):
    def setUp(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self._previous_cwd = Path.cwd()
        os.chdir(project_root)
        self.template_path = (
            project_root
            / "templates"
            / "texsmith-template-book"
            / "texsmith_template_book"
        )
        self.template = load_template(str(self.template_path))

    def tearDown(self) -> None:
        os.chdir(self._previous_cwd)

    def test_iter_assets_declares_required_files(self) -> None:
        assets = list(self.template.iter_assets())
        destinations = {asset.destination for asset in assets}

        self.assertIn(Path("covers"), destinations)
        self.assertIn(Path("covers/circles.tex"), destinations)
        self.assertIn(Path("titlepage.tex"), destinations)
        self.assertIn(Path("mkbook.cls"), destinations)

    def test_wrap_document_injects_mainmatter(self) -> None:
        body = "\\section{Demo}"
        wrapped = self.template.wrap_document(body)

        self.assertIn("\\mainmatter", wrapped)
        self.assertIn(body, wrapped)

    def test_manifest_defaults_are_applied(self) -> None:
        wrapped = self.template.wrap_document("")
        self.assertIn("\\def\\title{A LaTeX Book Template}", wrapped)
        self.assertIn("\\tableofcontents", wrapped)
        self.assertNotIn("\\makeglossaries", wrapped)
        self.assertNotIn("\\newacronym", wrapped)
        self.assertNotIn("\\makeindex", wrapped)
        self.assertNotIn("\\printindex", wrapped)

    def test_wrap_document_includes_index_when_flag_true(self) -> None:
        context = self.template.prepare_context("")
        context["index_entries"] = True
        wrapped = self.template.wrap_document("", context=context)
        self.assertIn("\\makeindex", wrapped)
        self.assertIn("\\printindex", wrapped)

    def test_wrap_document_includes_acronyms_when_present(self) -> None:
        context = self.template.prepare_context("")
        context["acronyms"] = {"HTTP": "Hypertext Transfer Protocol"}
        wrapped = self.template.wrap_document("", context=context)
        self.assertIn("\\makeglossaries", wrapped)
        self.assertIn("\\newacronym{HTTP}{HTTP}{Hypertext Transfer Protocol}", wrapped)
        self.assertIn("\\printglossary[type=\\acronymtype", wrapped)

    def test_copy_template_assets_materialises_payload(self) -> None:
        with TemporaryDirectory() as temp_dir:
            destination_root = Path(temp_dir)
            context = self.template.prepare_context("")
            copy_template_assets(self.template, destination_root, context=context)

            self.assertTrue((destination_root / "mkbook.cls").exists())
            circles = destination_root / "covers" / "circles.tex"
            self.assertTrue(circles.exists())
            content = circles.read_text(encoding="utf-8")
            self.assertNotIn("\\VAR{", content)
            self.assertNotIn("\\BLOCK", content)
            self.assertIn("\\def\\covercolor{indigo(dye)}", content)
            self.assertTrue((destination_root / "titlepage.tex").exists())

    def test_load_template_from_shortcut_path(self) -> None:
        shortcut = load_template("./book")
        self.assertEqual(shortcut.info.name, self.template.info.name)
        self.assertEqual(shortcut.info.entrypoint, self.template.info.entrypoint)
        slug = load_template("book")
        self.assertEqual(slug.info.name, self.template.info.name)


class ArticleTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self._previous_cwd = Path.cwd()
        os.chdir(project_root)
        self.template_path = (
            project_root
            / "templates"
            / "texsmith-template-article"
            / "texsmith_template_article"
        )
        self.template = load_template(str(self.template_path))

    def tearDown(self) -> None:
        os.chdir(self._previous_cwd)

    def test_documentclass_defaults(self) -> None:
        wrapped = self.template.wrap_document("")
        self.assertIn(r"\documentclass[a4paper]{article}", wrapped)
        self.assertNotIn("landscape]{article}", wrapped)
        self.assertIn(r"\geometry{margin=2.5cm,a4paper}", wrapped)
        self.assertNotIn("\\usepackage{imakeidx}", wrapped)
        self.assertNotIn("\\usepackage[acronym]{glossaries}", wrapped)
        self.assertNotIn("\\makeindex", wrapped)
        self.assertNotIn("\\printindex", wrapped)
        self.assertNotIn("\\newacronym", wrapped)

    def test_documentclass_overrides(self) -> None:
        overrides = {
            "paper": "a3",
            "orientation": "landscape",
            "title": "Demo Article",
            "author": "Alice Example",
        }
        wrapped = self.template.wrap_document("", overrides=overrides)
        self.assertIn(r"\documentclass[a3paper,landscape]{article}", wrapped)
        self.assertIn(r"\geometry{margin=2.5cm,a3paper,landscape}", wrapped)
        self.assertIn(r"\title{Demo Article}", wrapped)
        self.assertIn(r"\author{Alice Example}", wrapped)

    def test_load_template_from_shortcut_path(self) -> None:
        shortcut = load_template("./article")
        self.assertEqual(shortcut.info.name, self.template.info.name)
        slug = load_template("article")
        self.assertEqual(slug.info.name, self.template.info.name)

    def test_rejects_invalid_paper_option(self) -> None:
        with self.assertRaises(TemplateError):
            self.template.wrap_document("", overrides={"paper": "iso"})

    def test_rejects_invalid_orientation_option(self) -> None:
        with self.assertRaises(TemplateError):
            self.template.wrap_document("", overrides={"orientation": "diagonal"})

    def test_article_includes_index_when_flag_true(self) -> None:
        context = self.template.prepare_context("")
        context["index_entries"] = True
        wrapped = self.template.wrap_document("", context=context)
        self.assertIn("\\usepackage{imakeidx}", wrapped)
        self.assertIn("\\makeindex", wrapped)
        self.assertIn("\\printindex", wrapped)

    def test_article_includes_acronyms_when_present(self) -> None:
        context = self.template.prepare_context("")
        context["acronyms"] = {"HTTP": "Hypertext Transfer Protocol"}
        wrapped = self.template.wrap_document("", context=context)
        self.assertIn("\\usepackage[acronym]{glossaries}", wrapped)
        self.assertIn("\\makeglossaries", wrapped)
        self.assertIn("\\newacronym{HTTP}{HTTP}{Hypertext Transfer Protocol}", wrapped)
        self.assertIn("\\printglossary[type=\\acronymtype", wrapped)


if __name__ == "__main__":
    unittest.main()
