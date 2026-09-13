from __future__ import annotations

from pathlib import Path
import textwrap
from typing import Any

from bs4 import BeautifulSoup
import pytest

from texsmith.adapters.plugins import snippet
from texsmith.core.diagnostics import LoggingEmitter, NullEmitter
from texsmith.core.documents import Document
from texsmith.diagnostics import format_diagnostic


WADHWANI = (
    "@article{Wadhwani_2011, title={Improvement in melting and baking properties of "
    "low-fat Mozzarella cheese}, author={Wadhwani, R. and McMahon, D.J.}, year={2011}, "
    "doi={10.3168/jds.2010-3952}}\n"
)


def _build_snippet_block(tmp_path: Path, body: str) -> snippet.SnippetBlock:
    html = f"""
    <div class="snippet">
      <pre><code class="language-md">{body}</code></pre>
    </div>
    """
    soup = BeautifulSoup(textwrap.dedent(html), "html.parser")
    element = soup.find("div")
    assert element is not None
    host_path = tmp_path / "host.md"
    host_path.write_text("host", encoding="utf-8")
    block = snippet._extract_snippet_block(element, host_path=host_path)
    assert block is not None
    return block


def test_snippet_uses_press_template_override(tmp_path: Path) -> None:
    raw = """
    ---
    press:
      template: article
    ---
    # Hello
    """
    block = _build_snippet_block(tmp_path, textwrap.dedent(raw).strip())

    assert block.template_id == "article"
    assert "template" not in block.template_overrides.get("press", {})


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param(
            "bibliography:\n  WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952",
            id="legacy",
        ),
        pytest.param(
            "press:\n  sources:\n    bibliography:\n"
            "      WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952",
            id="press-sources",
        ),
    ],
)
def test_snippet_front_matter_bibliography_reaches_the_ir(tmp_path: Path, declaration: str) -> None:
    """A fence's ``bibliography:`` is front matter of the previewed document.

    The fence's YAML is read as snippet configuration and peeled off the body,
    so the keys that belong to the document have to be written back: the
    ``doi`` pass reads the *typed* front matter tmark parsed, not the legacy
    mapping, and without them a cited DOI came out as ``[?key]``.
    """
    raw = (
        "---\nwidth: 70%\n"
        f"{declaration}\n"
        "---\n# Introduction\n\n"
        "Cheese exhibits unique melting properties @WADHWANI20111713.\n"
    )
    block = _build_snippet_block(tmp_path, raw.strip())
    document = snippet._build_document(
        block, host_dir=tmp_path, host_name="host", emitter=NullEmitter()
    )

    assert document is not None
    assert document.ir is not None
    declared = document.ir.front_matter.keys.press.sources.bibliography
    assert declared == {"WADHWANI20111713": "https://doi.org/10.3168/jds.2010-3952"}
    # The preview's own configuration stays out of the document.
    assert "width" not in document.front_matter


def test_a_fence_registers_as_a_source_of_the_run(tmp_path: Path) -> None:
    """A diagnostic raised inside a fence names the fence, not the host page.

    The nested document used to parse against a file table of its own, so its
    pseudo-source took id 0 — the id the host document already held in the
    run's table. A finding inside the fence then rendered with the host's path
    and the fence's line number, which points at an unrelated line.
    """
    emitter = LoggingEmitter()
    host = tmp_path / "host.md"
    host.write_text("# Host\n\nThe host document.\n", encoding="utf-8")
    host_document = Document.from_markdown(host, emitter=emitter)
    assert host_document.ir is not None
    assert host_document.ir.file == 0

    block = _build_snippet_block(tmp_path, "# Fenced\n\nSee [[nowhere]] inside the fence.\n")
    nested = snippet._build_document(block, host_dir=tmp_path, host_name="host", emitter=emitter)

    assert nested is not None
    assert nested.ir is not None
    assert nested.files is emitter.sink.files
    assert nested.ir.file != host_document.ir.file
    assert emitter.sink.files.path(nested.ir.file) != host

    (record,) = [d for d in nested.diagnostics if d.code == "compat-unsupported"]
    rendered = format_diagnostic(record, emitter.sink.files)
    assert rendered.startswith(str(emitter.sink.files.path(nested.ir.file)))


def test_snippet_preview_resolves_a_front_matter_doi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The nested build cites the DOI entry instead of printing ``[?key]``.

    Everything but the LaTeX run is real: the fence is parsed, a
    :class:`~texsmith.core.templates.session.TemplateSession` converts the
    nested document, and the ``.tex`` it writes is what is inspected.
    """
    fetched: list[str] = []

    class FakeFetcher:
        def __init__(self, **kwargs: Any) -> None:
            del kwargs

        def fetch(self, value: str) -> str:
            fetched.append(value)
            return WADHWANI

    from texsmith.core.bibliography import doi as doi_module, loading as loading_module

    monkeypatch.setattr(doi_module, "DoiBibliographyFetcher", FakeFetcher)
    monkeypatch.setattr(loading_module, "resolve_bibliography_fetcher", FakeFetcher)
    # No user-level snippet cache: the preview is built, never looked up.
    monkeypatch.setattr(snippet, "_resolve_caches", lambda: [])
    # The work directory is kept so the generated sources can be read back.
    dump = tmp_path / "dump"
    monkeypatch.setenv("TEXSMITH_SNIPPET_DUMP_DIR", str(dump))

    def fake_compile(render_result: Any) -> Path:
        pdf = render_result.main_tex_path.with_suffix(".pdf")
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        return pdf

    def fake_preview(*args: Any, **kwargs: Any) -> None:
        del args, kwargs

    monkeypatch.setattr(snippet, "_compile_pdf", fake_compile)
    monkeypatch.setattr(snippet, "_pdf_to_png_grid", fake_preview)

    raw = """
    ---
    press:
      sources:
        bibliography:
          WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952
    ---
    # Introduction

    Cheese exhibits unique melting properties @WADHWANI20111713.
    """
    block = _build_snippet_block(tmp_path, textwrap.dedent(raw).strip())
    snippet.ensure_snippet_assets(
        block,
        output_dir=tmp_path / "snippets",
        source_path=tmp_path / "host.md",
    )

    assert fetched == ["https://doi.org/10.3168/jds.2010-3952"]
    work_dir = dump / block.asset_basename
    body = next(work_dir.glob("*.tex")).read_text("utf-8")
    assert "cite{WADHWANI20111713}" in body
    assert "[?WADHWANI20111713]" not in body
    # The pass wrote the fetched entry beside the nested document and the
    # conversion absorbed it, so biber has the entry the citation names.
    assert list(work_dir.glob("inline-doi-*.bib"))
    assert "Wadhwani" in (work_dir / "texsmith-bibliography.bib").read_text("utf-8")
