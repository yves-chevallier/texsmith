from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mkdocs_latex.config import BookConfig
from mkdocs_latex.renderer import LaTeXRenderer
from mkdocs_latex.transformers import register_converter, registry


class _StubConverter:
    def __init__(self, name: str, payload: bytes | str = "PDF"):
        self.name = name
        self.payload = payload

    def __call__(self, source, *, output_dir: Path, **_):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        artefact = output_dir / f"{self.name}.pdf"
        data = (
            self.payload.encode("utf-8")
            if isinstance(self.payload, str)
            else self.payload
        )
        artefact.write_bytes(data)
        return artefact


class MediaRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.config = BookConfig(project_dir=self.tmp_path)
        self.renderer = LaTeXRenderer(
            config=self.config,
            output_root=self.tmp_path / "build",
            parser="html.parser",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_drawio_image_conversion(self) -> None:
        source_file = self.tmp_path / "diagram.drawio"
        source_file.write_text("<mxfile />", encoding="utf-8")

        original = registry.get("drawio")
        register_converter("drawio", _StubConverter("diagram"))
        try:
            html = '<p><img src="diagram.drawio" alt="PGCD Diagram"></p>'
            latex = self.renderer.render(html, runtime={"source_dir": self.tmp_path})

            self.assertIn("\\includegraphics", latex)
            self.assertIn("diagram.pdf", latex)
            self.assertIn("PGCD Diagram", latex)

            assets = dict(self.renderer.assets.items())
            self.assertTrue(any("diagram.drawio" in key for key in assets))
        finally:
            register_converter("drawio", original)

    def test_mermaid_block_conversion(self) -> None:
        original = registry.get("mermaid")
        register_converter("mermaid", _StubConverter("mermaid"))
        try:
            html = """
            <div class="highlight">
                <pre><code>%% Influence Graph
flowchart LR
    A --> B
    B --> C
</code></pre>
            </div>
            """
            latex = self.renderer.render(html, runtime={"source_dir": self.tmp_path})

            self.assertIn("\\includegraphics", latex)
            self.assertIn("mermaid.pdf", latex)
            self.assertIn("Influence Graph", latex)

            assets = dict(self.renderer.assets.items())
            self.assertTrue(any(key.startswith("mermaid::") for key in assets))
        finally:
            register_converter("mermaid", original)


if __name__ == "__main__":
    unittest.main()
