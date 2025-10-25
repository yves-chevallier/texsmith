import base64
from pathlib import Path
import zlib

from PIL import Image  # type: ignore[import]
import pytest

from texsmith.config import BookConfig
from texsmith.latex import LaTeXRenderer
from texsmith.transformers import image2pdf, register_converter, registry


class _StubConverter:
    def __init__(self, name: str, payload: bytes | str = "PDF"):
        self.name = name
        self.payload = payload

    def __call__(self, source, *, output_dir: Path, **_):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        artefact = output_dir / f"{self.name}.pdf"
        data = self.payload.encode("utf-8") if isinstance(self.payload, str) else self.payload
        artefact.write_bytes(data)
        return artefact


@pytest.fixture
def renderer(tmp_path: Path) -> LaTeXRenderer:
    config = BookConfig(project_dir=tmp_path)
    return LaTeXRenderer(
        config=config,
        output_root=tmp_path / "build",
        parser="html.parser",
    )


def test_drawio_image_conversion(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    source_file = tmp_path / "diagram.drawio"
    source_file.write_text("<mxfile />", encoding="utf-8")

    original = registry.get("drawio")
    register_converter("drawio", _StubConverter("diagram"))
    try:
        html = '<p><img src="diagram.drawio" alt="PGCD Diagram"></p>'
        latex = renderer.render(html, runtime={"source_dir": tmp_path})

        assert "\\includegraphics" in latex
        assert "diagram.pdf" in latex
        assert "PGCD Diagram" in latex

        assets = dict(renderer.assets.items())
        assert any("diagram.drawio" in key for key in assets)
    finally:
        register_converter("drawio", original)


def test_mermaid_block_conversion(renderer: LaTeXRenderer, tmp_path: Path) -> None:
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
        latex = renderer.render(html, runtime={"source_dir": tmp_path})

        assert "\\includegraphics" in latex
        assert "mermaid.pdf" in latex
        assert "Influence Graph" in latex

        assets = dict(renderer.assets.items())
        assert any(key.startswith("mermaid::") for key in assets)
    finally:
        register_converter("mermaid", original)


def test_twemoji_image_conversion(renderer: LaTeXRenderer) -> None:
    original = registry.get("fetch-image")
    register_converter("fetch-image", _StubConverter("twemoji"))
    try:
        html = "<p><img class='twemoji' src='https://example.com/emoji.svg' alt='rocket'></p>"
        latex = renderer.render(html)
        assert "\\includegraphics[width=1em]" in latex
        assets = dict(renderer.assets.items())
        assert "https://example.com/emoji.svg" in assets
    finally:
        register_converter("fetch-image", original)


def test_twemoji_inline_svg_conversion(renderer: LaTeXRenderer) -> None:
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
        latex = renderer.render(html)
        assert "\\includegraphics[width=1em]" in latex
        assets = dict(renderer.assets.items())
        assert any(key.startswith("twemoji::") for key in assets)
    finally:
        register_converter("svg", original)


def test_mermaid_image_from_file(renderer: LaTeXRenderer, tmp_path: Path) -> None:
    source_file = tmp_path / "diagram.mmd"
    source_file.write_text("%% Local Diagram\nflowchart LR\n    A --> B\n", encoding="utf-8")

    original = registry.get("mermaid")
    register_converter("mermaid", _StubConverter("mermaid-file"))
    try:
        html = '<p><img src="diagram.mmd" alt="Alt caption"></p>'
        latex = renderer.render(html, runtime={"source_dir": tmp_path})

        assert "\\includegraphics" in latex
        assert "mermaid-file.pdf" in latex
        assert "Local Diagram" in latex

        assets = dict(renderer.assets.items())
        assert any(key.startswith("mermaid::") for key in assets)
    finally:
        register_converter("mermaid", original)


def test_mermaid_image_from_live_url(renderer: LaTeXRenderer) -> None:
    original = registry.get("mermaid")
    register_converter("mermaid", _StubConverter("mermaid-live"))
    try:
        diagram = "flowchart LR\n    A --> B\n"
        compressed = zlib.compress(diagram.encode("utf-8"))
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        url = f"https://mermaid.live/edit#pako:{encoded}"
        html = f'<p><img src="{url}" alt="Flowchart diagram"></p>'

        latex = renderer.render(html)

        assert "\\includegraphics" in latex
        assert "mermaid-live.pdf" in latex
        assert "Flowchart diagram" in latex

        assets = dict(renderer.assets.items())
        assert any(key.startswith("mermaid::") for key in assets)
    finally:
        register_converter("mermaid", original)


def test_bitmap_formats_are_normalised_to_pdf(tmp_path: Path) -> None:
    formats = {
        "tiff": "TIFF",
        "webp": "WEBP",
        "avif": "AVIF",
        "gif": "GIF",
        "png": "PNG",
        "bmp": "BMP",
    }
    output_dir = tmp_path / "build"
    produced: list[Path] = []
    for suffix, pil_format in formats.items():
        source = tmp_path / f"fixture.{suffix}"
        image = Image.new("RGB", (12, 12), color=(255, 0, 0))
        image.save(source, format=pil_format)
        image.close()

        artefact = image2pdf(source, output_dir=output_dir)
        assert artefact.exists(), f"{pil_format} failed to convert"
        assert artefact.suffix == ".pdf"
        produced.append(artefact)

    assert len({path.name for path in produced}) == len(formats), (
        "Expected unique artefacts for each input format"
    )
    assert all(path.stat().st_size > 0 for path in produced), "Converted PDFs must not be empty"
