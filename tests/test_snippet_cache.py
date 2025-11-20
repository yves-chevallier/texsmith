from __future__ import annotations

from pathlib import Path

from texsmith.adapters.plugins import snippet


def _build_block(content: str = "print('Hello')") -> snippet.SnippetBlock:
    overrides: dict[str, str] = {}
    digest = snippet._hash_payload(content, overrides)
    return snippet.SnippetBlock(
        content=content,
        caption=None,
        label=None,
        figure_width=None,
        template_overrides=overrides,
        digest=digest,
        border_enabled=True,
        dogear_enabled=True,
        transparent_corner=True,
    )


def test_ensure_snippet_assets_reuses_cached_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TEXSMITH_CACHE_DIR", str(tmp_path / "cache-root"))
    monkeypatch.setattr(snippet, "_SNIPPET_CACHE", None, raising=False)
    block = _build_block()

    cache = snippet._resolve_cache()
    assert cache is not None

    pdf_source = tmp_path / "prefill.pdf"
    png_source = tmp_path / "prefill.png"
    pdf_source.write_bytes(b"%PDF-TEST%")
    png_source.write_bytes(b"\x89PNG\r\n")
    cache.store(block.digest, pdf_source, png_source, template_version=None)
    cache.flush()

    compile_called = {"value": False}

    def _fail_compile(*_args, **_kwargs) -> Path:
        compile_called["value"] = True
        raise AssertionError("Snippet compilation should be skipped when cached assets exist.")

    monkeypatch.setattr(snippet, "_compile_pdf", _fail_compile)

    destination = tmp_path / "snippets"
    assets = snippet.ensure_snippet_assets(
        block,
        output_dir=destination,
        transparent_corner=False,
    )

    assert assets.pdf.read_bytes() == pdf_source.read_bytes()
    assert assets.png.read_bytes() == png_source.read_bytes()
    assert compile_called["value"] is False
