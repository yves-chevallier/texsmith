import types

from texsmith.adapters.handlers import _assets
from texsmith.adapters.transformers.strategies import (
    DrawioToPdfStrategy,
    MermaidToPdfStrategy,
)


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
    strategy = DrawioToPdfStrategy()

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

    monkeypatch.setattr(_assets, "drawio2pdf", fake_drawio)
    context = types.SimpleNamespace(
        assets=types.SimpleNamespace(output_root=tmp_path),
        runtime={"diagrams_backend": "docker"},
    )

    _assets._convert_local_asset(context, src, ".drawio")
    assert called["backend"] == "docker"
