import base64
from pathlib import Path
import shutil
import zlib

from PIL import Image  # type: ignore[import]
import pytest

from texsmith.adapters.transformers import image2pdf, register_converter, registry
import texsmith.adapters.transformers.strategies as strategies
from texsmith.core.conversion.core import convert_documents
from texsmith.core.conversion.models import ConversionRequest
from texsmith.core.documents import Document
from texsmith.core.exceptions import TransformerExecutionError


def render_markdown(tmp_path: Path, body: str, **request_options: object) -> tuple[str, dict]:
    """Render ``body`` through the passes and return ``(latex, asset map)``.

    The ``assets`` pass drives the converters of this module: it resolves each
    ``Image``, hands the file (or the Mermaid source) to the registered
    converter and rewrites ``src`` to the stored artefact.
    """
    source = tmp_path / "doc.md"
    source.write_text(body, encoding="utf-8")
    bundle = convert_documents(
        [Document.from_markdown(source)],
        output_dir=tmp_path / "build",
        settings=ConversionRequest(documents=[source], **request_options),
    )
    fragment = bundle.fragments[0]
    assert fragment.conversion is not None
    return fragment.latex, dict(fragment.conversion.assets_map)


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


_FAKE_PDF = b"%PDF-1.4\n1 0 obj<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer<<>>\nstartxref\n9\n%%EOF"


def _make_mermaid_cli(tmp_path: Path) -> Path:
    script = tmp_path / "mmdc"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "from pathlib import Path",
                "args = sys.argv[1:]",
                "target = None",
                "for idx, arg in enumerate(args):",
                "    if arg == '-o':",
                "        target = args[idx + 1]",
                "        break",
                "if target is None:",
                "    sys.exit(2)",
                "Path(target).write_text('mermaid-pdf', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _make_drawio_cli(tmp_path: Path) -> Path:
    script = tmp_path / "drawio"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "from pathlib import Path",
                "args = sys.argv[1:]",
                "output = None",
                "for idx, arg in enumerate(args):",
                "    if arg == '--output':",
                "        output = args[idx + 1]",
                "        break",
                "if output is None:",
                "    sys.exit(2)",
                "Path(output).write_text('drawio-pdf', encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_png_image_preserves_name_by_default(tmp_path: Path) -> None:
    source_file = tmp_path / "figure.png"
    Image.new("RGB", (16, 16), color="blue").save(source_file)

    latex, assets = render_markdown(tmp_path, "![Example Figure](figure.png)\n")

    assert "\\includegraphics" in latex
    assert "figure.png" in latex

    stored = assets[str(source_file)]
    assert stored.exists()
    assert stored.suffix.lower() == ".png"


def test_linked_image_wraps_includegraphics(tmp_path: Path) -> None:
    source_file = tmp_path / "linked.png"
    Image.new("RGB", (16, 16), color="blue").save(source_file)

    latex, assets = render_markdown(
        tmp_path,
        "[![Example Figure](linked.png){width=60%}](https://example.com)\n",
    )

    assert r"\href{https://example.com}{" in latex
    assert "\\includegraphics[width=0.6\\linewidth]" in latex
    assert "linked.png" in latex

    stored = next(path for key, path in assets.items() if key.startswith(str(source_file)))
    assert stored.exists()
    assert stored.suffix.lower() == ".png"


def test_mkdocs_theme_variants_are_stripped(tmp_path: Path) -> None:
    source_file = tmp_path / "logo.png"
    Image.new("RGB", (16, 16), color="red").save(source_file)

    for fragment in ("only-light", "only-dark"):
        work = tmp_path / fragment
        work.mkdir()
        Image.new("RGB", (16, 16), color="red").save(work / "logo.png")
        latex, assets = render_markdown(work, f"![Logo](logo.png#{fragment})\n")

        assert "\\includegraphics" in latex
        assert f"#{fragment}" not in latex
        assert assets[str(work / "logo.png")].exists()


def test_convert_assets_forces_png_conversion(tmp_path: Path) -> None:
    source_file = tmp_path / "diagram.png"
    Image.new("RGB", (16, 16), color="green").save(source_file)

    latex, assets = render_markdown(tmp_path, "![Converted](diagram.png)\n", convert_assets=True)

    assert "diagram.pdf" in latex
    assert assets[str(source_file)].suffix.lower() == ".pdf"


def test_drawio_image_conversion(tmp_path: Path) -> None:
    source_file = tmp_path / "diagram.drawio"
    source_file.write_text("<mxfile />", encoding="utf-8")

    original = registry.get("drawio")
    register_converter("drawio", _StubConverter("diagram"))
    try:
        latex, assets = render_markdown(tmp_path, "![PGCD Diagram](diagram.drawio)\n")

        assert "\\includegraphics" in latex
        assert "diagram.pdf" in latex
        assert "PGCD Diagram" in latex
        assert any("diagram.drawio" in key for key in assets)
    finally:
        register_converter("drawio", original)


def test_drawio_prefers_local_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = _make_drawio_cli(tmp_path)
    diagram = tmp_path / "diagram.drawio"
    diagram.write_text("<mxfile />", encoding="utf-8")

    monkeypatch.setattr(strategies, "normalise_pdf_version", lambda *_args, **_kwargs: None)

    def _fail_docker(*_args, **_kwargs):
        raise AssertionError("docker should not run when draw.io CLI is available")

    monkeypatch.setattr(strategies, "run_container", _fail_docker)
    real_which = shutil.which

    def _fake_which(name: str) -> str | None:
        if name in {"drawio", "draw.io"}:
            return str(script)
        return real_which(name)

    monkeypatch.setattr(shutil, "which", _fake_which)

    latex, _assets = render_markdown(tmp_path, "![Graph](diagram.drawio)\n")
    assert "\\includegraphics" in latex


def test_drawio_cli_warns_when_using_hint_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script_dir = tmp_path / "snap" / "bin"
    script_dir.mkdir(parents=True, exist_ok=True)
    script = _make_drawio_cli(script_dir)
    diagram = tmp_path / "diagram.drawio"
    diagram.write_text("<mxfile />", encoding="utf-8")

    monkeypatch.setattr(strategies, "DRAWIO_CLI_HINT_PATHS", (script,))
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    monkeypatch.setattr(strategies, "normalise_pdf_version", lambda *_args, **_kwargs: None)

    def _fail_docker(*_args, **_kwargs):
        raise AssertionError("docker should not run when hint executable is present")

    monkeypatch.setattr(strategies, "run_container", _fail_docker)

    with pytest.warns(UserWarning, match="drawio"):
        render_markdown(tmp_path, "![Graph](diagram.drawio)\n", diagrams_backend="local")


def test_drawio_cli_failure_falls_back_to_docker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    strategy = strategies.DrawioToPdfStrategy()
    source = tmp_path / "diagram.drawio"
    source.write_text("<mxfile />", encoding="utf-8")

    monkeypatch.setattr(strategies, "_resolve_cli", lambda *_: ("drawio-bin", True))

    def _fail_local(self, *_, **__):
        raise TransformerExecutionError("local draw.io failure")

    monkeypatch.setattr(strategies.DrawioToPdfStrategy, "_run_local_cli", _fail_local)
    monkeypatch.setattr(strategies, "normalise_pdf_version", lambda *_: None)

    def _fake_run_container(*_, mounts, **__):
        working_dir = Path(mounts[0].source)
        (working_dir / "diagram.pdf").write_bytes(_FAKE_PDF)

    monkeypatch.setattr(strategies, "run_container", _fake_run_container)

    target = strategy(source, output_dir=tmp_path / "build")
    assert target.exists()


def test_drawio_cli_and_docker_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    strategy = strategies.DrawioToPdfStrategy()
    source = tmp_path / "diagram.drawio"
    source.write_text("<mxfile />", encoding="utf-8")

    monkeypatch.setattr(strategies, "_resolve_cli", lambda *_: ("drawio-bin", True))

    def _fail_local(self, *_, **__):
        raise TransformerExecutionError("local draw.io failure")

    monkeypatch.setattr(strategies.DrawioToPdfStrategy, "_run_local_cli", _fail_local)

    def _fail_playwright(self, *_, **__):
        raise TransformerExecutionError("playwright unavailable")

    monkeypatch.setattr(strategies.DrawioToPdfStrategy, "_run_playwright", _fail_playwright)

    def _fail_docker(*_, **__):
        raise TransformerExecutionError("docker unavailable")

    monkeypatch.setattr(strategies, "run_container", _fail_docker)

    with pytest.raises(TransformerExecutionError) as excinfo:
        strategy(source, output_dir=tmp_path / "build")
    message = str(excinfo.value)
    assert "draw.io CLI failed" in message
    assert "Docker fallback also failed" in message


MERMAID_FENCE = "```mermaid\n%% Influence Graph\nflowchart LR\n    A --> B\n    B --> C\n```\n"


def test_mermaid_block_conversion(tmp_path: Path) -> None:
    original = registry.get("mermaid")
    register_converter("mermaid", _StubConverter("mermaid"))
    try:
        latex, assets = render_markdown(tmp_path, MERMAID_FENCE)

        assert "\\includegraphics" in latex
        assert "mermaid.pdf" in latex
        assert "Influence Graph" in latex
        assert any(key.startswith("mermaid::") for key in assets)
    finally:
        register_converter("mermaid", original)


def test_mermaid_block_falls_back_when_converter_fails(tmp_path: Path) -> None:
    original = registry.get("mermaid")

    def _failing_converter(*_args, **_kwargs):
        raise TransformerExecutionError("docker missing")

    register_converter("mermaid", _failing_converter)
    try:
        latex, _assets = render_markdown(tmp_path, MERMAID_FENCE)
        assert "[Influence Graph unavailable]" in latex
    finally:
        register_converter("mermaid", original)


def test_mermaid_prefers_local_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = _make_mermaid_cli(tmp_path)

    monkeypatch.setattr(strategies, "normalise_pdf_version", lambda *_args, **_kwargs: None)

    def _fail_docker(*_args, **_kwargs):
        raise AssertionError("docker should not run when local CLI is available")

    monkeypatch.setattr(strategies, "run_container", _fail_docker)
    real_which = shutil.which

    def _fake_which(name: str) -> str | None:
        if name == "mmdc":
            return str(script)
        return real_which(name)

    monkeypatch.setattr(shutil, "which", _fake_which)

    latex, _assets = render_markdown(tmp_path, MERMAID_FENCE, diagrams_backend="local")
    assert "\\includegraphics" in latex


def test_mermaid_cli_warns_when_using_hint_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script_dir = tmp_path / "snap" / "bin"
    script_dir.mkdir(parents=True, exist_ok=True)
    script = _make_mermaid_cli(script_dir)

    monkeypatch.setattr(strategies, "MERMAID_CLI_HINT_PATHS", (script,))
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    def _fail_play(*_a, **_k):
        raise TransformerExecutionError("playwright missing")

    monkeypatch.setattr(strategies.MermaidToPdfStrategy, "_run_playwright", _fail_play)

    monkeypatch.setattr(strategies, "normalise_pdf_version", lambda *_args, **_kwargs: None)

    def _fail_docker(*_args, **_kwargs):
        raise AssertionError("docker should not run when hint executable is present")

    monkeypatch.setattr(strategies, "run_container", _fail_docker)

    with pytest.warns(UserWarning, match="mmdc"):
        render_markdown(tmp_path, MERMAID_FENCE, diagrams_backend="local")


def test_mermaid_cli_failure_falls_back_to_docker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    strategy = strategies.MermaidToPdfStrategy()
    monkeypatch.setattr(strategies, "_resolve_cli", lambda *_: ("mmdc-bin", True))
    monkeypatch.setattr(strategies.shutil, "which", lambda *_: "docker")

    def _fail_play(*_a, **_k):
        raise TransformerExecutionError("playwright missing")

    monkeypatch.setattr(strategies.MermaidToPdfStrategy, "_run_playwright", _fail_play)

    def _fail_local(self, *_, **__):
        raise TransformerExecutionError("local mermaid failure")

    monkeypatch.setattr(strategies.MermaidToPdfStrategy, "_run_local_cli", _fail_local)
    monkeypatch.setattr(strategies, "normalise_pdf_version", lambda *_: None)

    def _fake_run_container(*_, mounts, args, **__):
        working_dir = Path(mounts[0].source)
        try:
            output_name = args[args.index("-o") + 1]
        except (ValueError, IndexError):
            output_name = "diagram.pdf"
        (working_dir / output_name).write_bytes(_FAKE_PDF)

    monkeypatch.setattr(strategies, "run_container", _fake_run_container)

    target = strategy("graph LR; A-->B", output_dir=tmp_path / "build")
    assert target.exists()


def test_mermaid_cli_and_docker_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    strategy = strategies.MermaidToPdfStrategy()
    monkeypatch.setattr(strategies, "_resolve_cli", lambda *_: ("mmdc-bin", True))
    monkeypatch.setattr(strategies.shutil, "which", lambda *_: "docker")

    def _fail_play(*_a, **_k):
        raise TransformerExecutionError("playwright missing")

    monkeypatch.setattr(strategies.MermaidToPdfStrategy, "_run_playwright", _fail_play)

    def _fail_local(self, *_, **__):
        raise TransformerExecutionError("local mermaid failure")

    monkeypatch.setattr(strategies.MermaidToPdfStrategy, "_run_local_cli", _fail_local)

    def _fail_docker(*_, **__):
        raise TransformerExecutionError("docker unavailable")

    monkeypatch.setattr(strategies, "run_container", _fail_docker)

    with pytest.raises(TransformerExecutionError) as excinfo:
        strategy("graph LR; A-->B", output_dir=tmp_path / "build")
    message = str(excinfo.value)
    assert "Mermaid CLI failed" in message
    assert "Docker fallback also failed" in message


def test_unicode_accents_are_emitted_by_default(tmp_path: Path) -> None:
    latex, _assets = render_markdown(tmp_path, "éclair --- ligature œ\n")

    assert "éclair --- ligature œ" in latex


def test_mermaid_image_from_file(tmp_path: Path) -> None:
    source_file = tmp_path / "diagram.mmd"
    source_file.write_text("%% Local Diagram\nflowchart LR\n    A --> B\n", encoding="utf-8")

    original = registry.get("mermaid")
    register_converter("mermaid", _StubConverter("mermaid-file"))
    try:
        latex, assets = render_markdown(tmp_path, "![Alt caption](diagram.mmd)\n")

        assert "\\includegraphics" in latex
        assert "mermaid-file.pdf" in latex
        assert "Local Diagram" in latex
        assert any(key.startswith("mermaid::") for key in assets)
    finally:
        register_converter("mermaid", original)


def test_mermaid_image_from_live_url(tmp_path: Path) -> None:
    original = registry.get("mermaid")
    register_converter("mermaid", _StubConverter("mermaid-live"))
    try:
        diagram = "flowchart LR\n    A --> B\n"
        compressed = zlib.compress(diagram.encode("utf-8"))
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
        url = f"https://mermaid.live/edit#pako:{encoded}"

        latex, assets = render_markdown(tmp_path, f"![Flowchart diagram]({url})\n")

        assert "\\includegraphics" in latex
        assert "mermaid-live.pdf" in latex
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
