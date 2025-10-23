import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zlib

from PIL import Image  # type: ignore[import]

from texsmith.config import BookConfig
from texsmith.renderer import LaTeXRenderer
from texsmith.transformers import image2pdf, register_converter, registry


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

    def test_twemoji_image_conversion(self) -> None:
        original = registry.get("fetch-image")
        register_converter("fetch-image", _StubConverter("twemoji"))
        try:
            html = (
                "<p><img class='twemoji' src='https://example.com/emoji.svg'"
                " alt='rocket'></p>"
            )
            latex = self.renderer.render(html)
            self.assertIn("\\includegraphics[width=1em]", latex)
            assets = dict(self.renderer.assets.items())
            self.assertIn("https://example.com/emoji.svg", assets)
        finally:
            register_converter("fetch-image", original)

    def test_twemoji_inline_svg_conversion(self) -> None:
        original = registry.get("svg")
        register_converter("svg", _StubConverter("twemoji-inline"))
        try:
            html = """
            <p>
                <span class="twemoji" title="sparkles">
                    <svg xmlns="http://www.w3.org/2000/svg"><path d="M0"/></svg>
                </span>
            </p>
            """
            latex = self.renderer.render(html)
            self.assertIn("\\includegraphics[width=1em]", latex)
            assets = dict(self.renderer.assets.items())
            self.assertTrue(any(key.startswith("twemoji::") for key in assets))
        finally:
            register_converter("svg", original)

    def test_mermaid_image_from_file(self) -> None:
        source_file = self.tmp_path / "diagram.mmd"
        source_file.write_text(
            "%% Local Diagram\nflowchart LR\n    A --> B\n", encoding="utf-8"
        )

        original = registry.get("mermaid")
        register_converter("mermaid", _StubConverter("mermaid-file"))
        try:
            html = '<p><img src="diagram.mmd" alt="Alt caption"></p>'
            latex = self.renderer.render(html, runtime={"source_dir": self.tmp_path})

            self.assertIn("\\includegraphics", latex)
            self.assertIn("mermaid-file.pdf", latex)
            self.assertIn("Local Diagram", latex)

            assets = dict(self.renderer.assets.items())
            self.assertTrue(any(key.startswith("mermaid::") for key in assets))
        finally:
            register_converter("mermaid", original)

    def test_mermaid_image_from_live_url(self) -> None:
        original = registry.get("mermaid")
        register_converter("mermaid", _StubConverter("mermaid-live"))
        try:
            diagram = "flowchart LR\n    A --> B\n"
            compressed = zlib.compress(diagram.encode("utf-8"))
            encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
            url = f"https://mermaid.live/edit#pako:{encoded}"
            html = f'<p><img src="{url}" alt="Flowchart diagram"></p>'

            latex = self.renderer.render(html)

            self.assertIn("\\includegraphics", latex)
            self.assertIn("mermaid-live.pdf", latex)
            self.assertIn("Flowchart diagram", latex)

            assets = dict(self.renderer.assets.items())
            self.assertTrue(any(key.startswith("mermaid::") for key in assets))
        finally:
            register_converter("mermaid", original)


class ImageConversionTests(unittest.TestCase):
    FORMATS = {
        "tiff": "TIFF",
        "webp": "WEBP",
        "avif": "AVIF",
        "gif": "GIF",
        "png": "PNG",
        "bmp": "BMP",
    }

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.output_dir = self.tmp_path / "build"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bitmap_formats_are_normalised_to_pdf(self) -> None:
        produced: list[Path] = []
        for suffix, pil_format in self.FORMATS.items():
            source = self.tmp_path / f"fixture.{suffix}"
            image = Image.new("RGB", (12, 12), color=(255, 0, 0))
            image.save(source, format=pil_format)
            image.close()

            artefact = image2pdf(source, output_dir=self.output_dir)
            self.assertTrue(artefact.exists(), f"{pil_format} failed to convert")
            self.assertEqual(artefact.suffix, ".pdf")
            produced.append(artefact)

        self.assertEqual(
            len({path.name for path in produced}),
            len(self.FORMATS),
            "Expected unique artefacts for each input format",
        )
        self.assertTrue(
            all(path.stat().st_size > 0 for path in produced),
            "Converted PDFs must not be empty",
        )


if __name__ == "__main__":
    unittest.main()
