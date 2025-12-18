from __future__ import annotations

from pathlib import Path

from texsmith.adapters.plugins import snippet


def _build_block(content: str = "print('Hello')") -> snippet.SnippetBlock:
    overrides: dict[str, str] = {}
    digest = snippet._hash_payload(
        content,
        overrides,
        cwd=None,
        template_id=None,
        layout=None,
        sources=[],
        promote_title=True,
        drop_title=False,
        suppress_title=False,
    )
    return snippet.SnippetBlock(
        content=content,
        sources=[],
        layout=None,
        preview_dogear=False,
        preview_fold_size=None,
        template_id=None,
        cwd=None,
        caption=None,
        label=None,
        figure_width=None,
        template_overrides=overrides,
        digest=digest,
        bibliography_files=[],
        promote_title=True,
        drop_title=False,
        suppress_title_metadata=False,
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
    )

    assert assets.pdf.read_bytes() == pdf_source.read_bytes()
    assert assets.png.read_bytes() == png_source.read_bytes()
    assert compile_called["value"] is False


def test_cache_store_records_markdown_and_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TEXSMITH_CACHE_DIR", str(tmp_path / "cache-root"))
    monkeypatch.setattr(snippet, "_SNIPPET_CACHE", None, raising=False)
    block = _build_block("body")
    cache = snippet._resolve_cache()
    assert cache is not None

    pdf_source = tmp_path / "prefill.pdf"
    png_source = tmp_path / "prefill.png"
    pdf_source.write_bytes(b"%PDF-TEST%")
    png_source.write_bytes(b"\x89PNG\r\n")
    source_path = tmp_path / "docs" / "host.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("host", encoding="utf-8")

    cache.store(
        block.digest,
        pdf_source,
        png_source,
        template_version="v1",
        block=block,
        source_path=source_path,
    )

    entry = cache.metadata["entries"][block.digest]
    md_name = entry["files"].get("md")
    md_path = cache.root / md_name
    assert md_path.exists()
    assert md_path.read_text(encoding="utf-8") == block.content
    assert entry["source"] == str(source_path)
    assert entry["attributes"]["figure_width"] is None
    assert entry["attributes"]["layout"] is None
    assert entry["files"]["pdf"] == snippet.asset_filename(block.digest, ".pdf")
    assert (cache.root / entry["files"]["pdf"]).read_bytes() == pdf_source.read_bytes()
