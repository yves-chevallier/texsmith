from texsmith.adapters.transformers.strategies import (
    DrawioStrategy,
    MermaidToPdfStrategy,
)
from texsmith.core.context import AssetRegistry
from texsmith.writers.latex import assets as _assets
from texsmith.writers.latex.assets import AssetOptions


def _raise(*args, **kwargs):
    raise RuntimeError


_FAKE_PDF = (
    b"%PDF-1.4\n%aaaa\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Count 0 >>\nendobj\nxref\n0 3\n"
    b"0000000000 65535 f \n0000000010 00000 n \n0000000061 00000 n \n"
    b"trailer\n<< /Root 1 0 R /Size 3 >>\nstartxref\n102\n%%EOF"
)


def test_drawio_playwright_backend(tmp_path, monkeypatch):
    src = tmp_path / "diagram.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    strategy = DrawioStrategy()

    def fake_play(source, *, target, cache_dir, format_opt, theme, **_):
        target.write_bytes(_FAKE_PDF)

    monkeypatch.setattr(strategy, "_run_playwright", fake_play)
    monkeypatch.setattr(
        "texsmith.adapters.transformers.strategies.normalise_pdf_version",
        lambda *_a, **_k: None,
    )

    # Avoid hitting local/ docker
    def _raise(*args, **kwargs):
        raise RuntimeError

    monkeypatch.setattr(strategy, "_run_local_cli", _raise)
    monkeypatch.setattr("texsmith.adapters.transformers.strategies.run_container", _raise)

    result = strategy(src, output_dir=tmp_path, backend="playwright")
    assert result.exists()


def test_mermaid_playwright_backend(tmp_path, monkeypatch):
    src = tmp_path / "diagram.mmd"
    src.write_text("graph TD; A-->B;", encoding="utf-8")
    strategy = MermaidToPdfStrategy()

    def fake_play(content, *, target, format_opt, theme, mermaid_config=None, **_):
        target.write_bytes(_FAKE_PDF)

    monkeypatch.setattr(strategy, "_run_playwright", fake_play)
    monkeypatch.setattr(
        "texsmith.adapters.transformers.strategies.normalise_pdf_version",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(strategy, "_run_local_cli", _raise)
    monkeypatch.setattr("texsmith.adapters.transformers.strategies.run_container", _raise)

    result = strategy(src, output_dir=tmp_path, backend="playwright")
    assert result.exists()


def test_diagrams_backend_propagates_to_converters(tmp_path, monkeypatch):
    src = tmp_path / "diagram.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")

    called = {}

    def fake_drawio(source, output_dir, **options):
        called["backend"] = options.get("backend")
        target = output_dir / "out.pdf"
        target.write_text("ok", encoding="utf-8")
        return target

    monkeypatch.setattr(_assets, "drawio_export", fake_drawio)
    opts = AssetOptions(
        assets=AssetRegistry(output_root=tmp_path),
        source_dir=tmp_path,
        document_path=tmp_path / "doc.md",
        diagrams_backend="docker",
    )

    _assets._convert_local_asset(opts, src, ".drawio")
    assert called["backend"] == "docker"


def test_drawio_crop_option_reaches_every_backend(tmp_path, monkeypatch):
    """``crop`` is normalised once and honoured identically by all backends."""
    src = tmp_path / "diagram.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    strategy = DrawioStrategy()
    seen: dict[str, object] = {}

    def fake_play(source, *, target, cache_dir, format_opt, theme, crop=True, **_):
        seen["playwright_crop"] = crop
        target.write_bytes(_FAKE_PDF)

    def fake_cli(command, **_kwargs):
        seen["cli_crop"] = "--crop" in command

    monkeypatch.setattr(strategy, "_run_playwright", fake_play)
    monkeypatch.setattr("texsmith.adapters.transformers.strategies._run_cli", fake_cli)
    monkeypatch.setattr(
        "texsmith.adapters.transformers.strategies.normalise_pdf_version",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr("texsmith.adapters.transformers.strategies.run_container", _raise)

    strategy(src, output_dir=tmp_path, backend="playwright")
    assert seen["playwright_crop"] is True

    # ``crop=false`` arrives as a string from an ``attr_list`` attribute.
    strategy(src, output_dir=tmp_path, backend="playwright", crop="false")
    assert seen["playwright_crop"] is False

    strategy._run_local_cli(
        "drawio",
        working_dir=tmp_path,
        source_name=src.name,
        output_name="out.pdf",
        options={"format": "pdf"},
    )
    assert seen["cli_crop"] is True

    strategy._run_local_cli(
        "drawio",
        working_dir=tmp_path,
        source_name=src.name,
        output_name="out.pdf",
        options={"format": "pdf", "crop": False},
    )
    assert seen["cli_crop"] is False


def test_drawio_crop_attribute_flows_from_the_image_to_the_converter(tmp_path, monkeypatch):
    """``![x](d.drawio){crop=false}`` reaches ``drawio_export`` and keys its own asset."""
    src = tmp_path / "diagram.drawio"
    src.write_text("<mxfile/>", encoding="utf-8")
    seen: list[object] = []

    def fake_drawio(source, output_dir, **options):
        seen.append(options.get("crop"))
        target = output_dir / f"out-{len(seen)}.pdf"
        target.write_text("ok", encoding="utf-8")
        return target

    monkeypatch.setattr(_assets, "drawio_export", fake_drawio)
    opts = AssetOptions(
        assets=AssetRegistry(output_root=tmp_path),
        source_dir=tmp_path,
        document_path=tmp_path / "doc.md",
    )

    _assets._convert_local_asset(opts, src, ".drawio")
    _assets._convert_local_asset(opts, src, ".drawio", {"crop": "false"})
    assert seen == [True, False]

    # A document-wide default still loses against the image attribute.
    opts.drawio_crop = False
    _assets._convert_local_asset(opts, src, ".drawio")
    _assets._convert_local_asset(opts, src, ".drawio", {"crop": "true"})
    assert seen[2:] == [False, True]

    assert _assets._asset_key(src, None) != _assets._asset_key(src, {"crop": "false"})
