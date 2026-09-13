"""The IR path end to end: the tmark reader on the examples (no PDF build).

The bodies come from ``tmark.write``; the template wrapping is the legacy
one. The ``ts-*`` contract macros (``\\tsacr``, ``\\tscodeinline``, …) are
asserted in the written ``.tex``; whether the fragments define them is the
engine's business and is not run here.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest
from typer.testing import CliRunner

from texsmith.core.context import DocumentState
from texsmith.core.conversion import ConversionRequest, resolution
from texsmith.core.conversion.bodies import Requires, build_writer_options
from texsmith.core.conversion.pipeline import include_search_path
from texsmith.core.conversion.resolution import (
    NUMBERING_OVERRIDE_KEY,
    PREDECLARED_SERIES,
    ResolutionChain,
    bibliography_paths,
    numbering_mode,
    resolve_numbering,
    tmark_language,
    writer_numbering,
)
from texsmith.core.conversion.service import ConversionService
from texsmith.core.documents import Document
from texsmith.core.fragments.activation import apply_requires, required_fragment
from texsmith.ir import model
from texsmith.ui.cli import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = PROJECT_ROOT / "examples"


def _render(args: list[str]) -> None:
    result = CliRunner().invoke(app, args, catch_exceptions=False)
    assert result.exit_code == 0, result.output


def _body(tex: Path) -> str:
    text = tex.read_text(encoding="utf-8")
    start = text.index("\\begin{document}")
    end = text.index("\\end{document}")
    return text[start:end]


def test_abbr_example_renders_acronyms_from_tmark(tmp_path: Path) -> None:
    out = tmp_path / "abbr"
    _render(
        [
            str(EXAMPLES / "abbr" / "abbreviations.md"),
            "-o",
            str(out),
            "-t",
            "article",
        ]
    )
    body = _body(out / "abbreviations.tex")
    assert "\\tsacr{NMR}" in body
    assert "\\tsacr{GCMS}" in body
    assert "\\acrshort{" not in body  # not the legacy writer
    # The promoted title left the body; ``Requires.fragments`` activated ts-glossary.
    assert "\\section{Abbreviations}" not in body
    assert "\\printglossary" in body
    assert (out / "ts-glossary.sty").exists()
    assert "\\newacronym{GCMS}" in (out / "ts-glossary.sty").read_text(encoding="utf-8")


def test_counters_example_numbers_through_resolve(tmp_path: Path) -> None:
    out = tmp_path / "counters"
    _render(
        [
            str(EXAMPLES / "counters" / "counters.md"),
            "-o",
            str(out),
            "-t",
            "article",
        ]
    )
    body = _body(out / "counters.tex")
    assert "\\section{Scope}" in body  # implicit ids are labelled only when referenced (C38)
    assert "\\subsection{Summary}" in body
    assert "\\label{fw:watchdog}FW-01" in body
    assert "\\label{req:log-retention}REQ-103" in body
    assert "\\hyperref[fw:watchdog]{FW-01}" in body
    assert "\\tscodeinline{press.declare.counters}" in body
    assert "\\begin{tabularx}" in body
    # Undeclared prefixes survive verbatim.
    assert "node.id" in body


def test_code_example_highlights_through_the_pass(tmp_path: Path) -> None:
    out = tmp_path / "code"
    _render(
        [
            str(EXAMPLES / "code" / "code-block.md"),
            "-o",
            str(out),
            "-t",
            "article",
        ]
    )
    body = _body(out / "code-block.tex")
    # Decision X3: the writer prints the Div{code} as a tscode environment
    # around the Pygments Verbatim payload of the highlight pass.
    assert "\\begin{tscode}[lang=py, title={Bubble Sort Algorithm}, engine=pygments]" in body
    assert "\\begin{tscode}[lang=javascript, linenums, engine=pygments]" in body
    assert "\\begin{tscode}[lang=lisp, hl_lines={2-3}, engine=pygments]" in body
    assert "\\begin{Verbatim}[commandchars=\\\\\\{\\}" in body
    assert "highlightlines={2-3}" in body
    assert "\\PY{k}{def}" in body
    assert "\\PY{n+nf}{bubble\\PYZus{}sort}" in body
    # The style definitions reach ts-code through the document state.
    assert "\\PY@reset" in (out / "ts-code.sty").read_text(encoding="utf-8")


def test_features_example_splices_the_fence_include(tmp_path: Path) -> None:
    out = tmp_path / "features"
    _render(
        [
            str(EXAMPLES / "markdown" / "features.md"),
            "-o",
            str(out),
            "-t",
            "article",
        ]
    )
    body = _body(out / "features.tex")
    # ``--8<-- "hanoi.py"`` inside the python fence: the include pass read the file.
    assert "\\PY{n+nf}{tower\\PYZus{}of\\PYZus{}hanoi}" in body
    assert "[include:" not in body


def _page_with_a_far_include(tmp_path: Path, front_matter: str = "") -> tuple[Path, Path]:
    """A page whose include only resolves from ``tmp_path``; returns ``(page, out)``."""
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "note.md").write_text("Far and away.\n", encoding="utf-8")
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "page.md"
    page.write_text(f"{front_matter}# Page\n\n{{include}}(shared/note.md)\n", encoding="utf-8")
    return page, tmp_path / "out"


def test_include_path_option_resolves_what_the_page_directory_misses(tmp_path: Path) -> None:
    page, out = _page_with_a_far_include(tmp_path)
    _render([str(page), "-o", str(out), "-t", "article", "--include-path", str(tmp_path)])
    body = _body(out / "page.tex")
    assert "Far and away." in body
    assert "[include:" not in body


def test_front_matter_include_paths_resolve_relative_to_the_document(tmp_path: Path) -> None:
    page, out = _page_with_a_far_include(
        tmp_path, front_matter="---\npress:\n  include_paths:\n    - ..\n---\n\n"
    )
    _render([str(page), "-o", str(out), "-t", "article"])
    body = _body(out / "page.tex")
    assert "Far and away." in body
    assert "[include:" not in body


def test_include_search_path_orders_and_normalises_its_sources(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "page.md"
    page.write_text(
        "---\npress:\n  include_paths:\n    - ../shared\n---\n\n# Page\n",
        encoding="utf-8",
    )
    document = Document.from_markdown(page)

    # Nothing but the front matter without a request.
    assert include_search_path(None, document) == (tmp_path / "shared",)

    # ``--include-path`` leads, the front matter follows, the host's comes last;
    # a directory named twice keeps its first place.
    request = ConversionRequest(
        include_paths=[tmp_path / "cli"],
        default_include_paths=[tmp_path / "site", tmp_path / "cli"],
    )
    assert include_search_path(request, document) == (
        tmp_path / "cli",
        tmp_path / "shared",
        tmp_path / "site",
    )

    # A relative entry of the request is read from the current directory.
    relative = ConversionRequest(include_paths=[Path("elsewhere")])
    assert include_search_path(relative, document) == (
        Path.cwd() / "elsewhere",
        tmp_path / "shared",
    )


def _fake_snippet_renderer(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the nested LaTeX build with placeholder assets; returns the fence contents seen."""
    from texsmith.adapters.plugins.snippet import SnippetAssets
    from texsmith.passes import snippet as snippet_pass

    seen: list[str] = []

    def render(block, *, output_dir: Path, source_path: Path, emitter) -> SnippetAssets:
        del source_path, emitter
        seen.append(block.content or "")
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf = output_dir / f"{block.asset_basename}.pdf"
        png = output_dir / f"{block.asset_basename}.png"
        pdf.write_bytes(b"%PDF-1.4")
        png.write_bytes(b"\x89PNG\r\n")
        return SnippetAssets(pdf=pdf, png=png)

    monkeypatch.setattr(snippet_pass, "render_snippet_assets", render)
    return seen


def test_snippet_example_renders_the_previews(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _fake_snippet_renderer(monkeypatch)
    out = tmp_path / "snippet"
    _render(
        [
            str(EXAMPLES / "snippet" / "docs" / "index.md"),
            "-o",
            str(out),
            "-t",
            "article",
        ]
    )
    body = _body(out / "index.tex")
    # Both fences (one nested in a four-backtick fence) became figures with
    # the caption and the width the info string carried; the previews are
    # rendered into ``snippets/`` and stored by the assets pass under ``assets/``.
    assert seen == [
        "Hello **World**!",
        '```c\n#include <stdio.h>\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}\n```',
    ]
    assert body.count("\\begin{figure}") == 2
    assert body.count("\\includegraphics[width=0.8\\linewidth]{assets/") == 2
    assert body.count("\\caption[Demo]{Demo}") == 2
    assert "\\begin{tscode}" not in body and "Hello **World**" not in body
    assert "[asset:" not in body
    assert len(list((out / "snippets").glob("snippet-*.pdf"))) == 2
    stored = sorted(path.name for path in (out / "assets").glob("*.pdf"))
    assert len(stored) == 2
    for name in stored:
        assert f"{{assets/{name}}}" in body


def test_snippet_example_typst_takes_the_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_snippet_renderer(monkeypatch)
    out = tmp_path / "snippet-typst"
    _render(
        [
            str(EXAMPLES / "snippet" / "docs" / "index.md"),
            "--format",
            "typst",
            "-o",
            str(out),
        ]
    )
    typ = (out / "index.typ").read_text(encoding="utf-8")
    assert typ.count('image("assets/') == 2
    assert typ.count('.png", width: 80%)') == 2
    assert "caption: [Demo]" in typ and "[asset:" not in typ


def test_typst_hello_example_writes_a_typst_body(tmp_path: Path) -> None:
    out = tmp_path / "hello"
    _render(
        [
            str(EXAMPLES / "typst-hello" / "hello.md"),
            "--format",
            "typst",
            "-o",
            str(out),
        ]
    )
    typ = (out / "hello.typ").read_text(encoding="utf-8")
    assert "= Hello Typst" in typ  # implicit ids are labelled only when referenced (C38)
    assert "#ts-divider()" in typ
    assert "#let ts-divider()" in typ  # the contract prelude is inlined
    assert '#link("https://typst.app")[link]' in typ
    assert "Hello Typst" in typ.split("= Hello Typst")[0]  # the standalone title line


def test_typst_templated_uses_the_scaffolding(tmp_path: Path) -> None:
    out = tmp_path / "hello-article"
    _render(
        [
            str(EXAMPLES / "typst-hello" / "hello.md"),
            "--format",
            "typst",
            "-t",
            "article",
            "-o",
            str(out),
        ]
    )
    typ = (out / "hello.typ").read_text(encoding="utf-8")
    assert "#set document(" in typ
    assert "= Hello Typst" in typ
    assert "#let ts-divider()" in typ


def test_debug_ir_dumps_the_ir(tmp_path: Path) -> None:
    out = tmp_path / "dbg"
    _render(
        [
            "--debug-ir",
            str(EXAMPLES / "abbr" / "abbreviations.md"),
            "-o",
            str(out),
            "-t",
            "article",
        ]
    )
    dump = json.loads((out / "abbreviations.ir.json").read_text(encoding="utf-8"))
    assert dump["blocks"][0]["type"] == "Header"
    assert [entry["key"] for entry in dump["abbreviations"]][:2] == ["NMR", "FTIR"]


def test_tmark_reads_every_markdown_source(tmp_path: Path) -> None:
    out = tmp_path / "default"
    _render([str(EXAMPLES / "abbr" / "abbreviations.md"), "-o", str(out), "-t", "article"])
    body = _body(out / "abbreviations.tex")
    assert "\\tsacr{" in body


def test_counter_start_is_chained_across_a_batch(tmp_path: Path) -> None:
    # The root ``counters`` spelling (deprecated, accepted) rather than ``press``:
    # a batch allows a single ``press`` source.
    front = '---\ncounters:\n  fw:\n    format: "FW-{n:02d}"\n---\n'
    first = tmp_path / "one.md"
    second = tmp_path / "two.md"
    first.write_text(front + "# One\n\nFinding #(fw:a) and #(fw:b).\n", encoding="utf-8")
    second.write_text(front + "# Two\n\nFinding #(fw:c).\n", encoding="utf-8")
    request = ConversionRequest(
        documents=[first, second],
        template="article",
        render_dir=tmp_path / "out",
        embed_fragments=True,
    )
    response = ConversionService().execute(request)
    tex = response.render_result.main_tex_path.read_text(encoding="utf-8")
    assert "\\label{fw:a}FW-01" in tex
    assert "\\label{fw:b}FW-02" in tex
    assert "\\label{fw:c}FW-03" in tex  # continues after the first document


def test_resolution_chain_advances_from_next_start(tmp_path: Path) -> None:
    chain = ResolutionChain(bibliography=bibliography_paths(["refs.bib", "refs.bib", "/abs/x.bib"]))
    assert chain.bibliography == (Path.cwd() / "refs.bib", Path("/abs/x.bib"))
    chain.advance({"next_start": {"fw": 6, "req": 104, "bad": "x"}})
    assert chain.start == {"fw": 6, "req": 104}
    document_path = tmp_path / "doc.md"

    class _Doc:
        source_path = document_path

    options = chain.options_for(_Doc())  # type: ignore[arg-type]
    payload = options.to_json()
    assert payload["path"] == str(document_path.resolve())
    assert payload["start"] == {"fw": 6, "req": 104}
    assert payload["bibliography"][1] == "/abs/x.bib"


def test_writer_options_map_the_template_context() -> None:
    options = build_writer_options(
        backend="latex",
        language="fr",
        code_options={"engine": "minted", "inline": {"plain": True, "breaks": "-/"}},
        legacy_accents=True,
        base_level=0,
        numbered=False,
        refs={"textual_print": "{text} ({number})"},
        numbering={"fw": "tmark"},
    )
    assert options == {
        "media": "print",
        "lang": "fr",
        "code": {"engine": "minted", "inline_plain": True, "inline_breaks": "-/"},
        "latex": {"legacy_accents": True},
        "headings": {"base_level": 0, "numbered": False},
        "refs": {"textual_print": "{text} ({number})"},
        "numbering": {"fw": "tmark"},
        "source_map": False,
    }
    assert build_writer_options(backend="html")["media"] == "web"
    assert (
        build_writer_options(backend="latex", code_options={"engine": "nope"})["code"]["engine"]
        == "pygments"
    )


def test_requires_union_and_activation() -> None:
    a = Requires.from_json(
        {
            "packages": ["booktabs", "glossaries"],
            "fragments": ["ts-glossary"],
            "acronyms": ["NMR"],
            "citations": ["knuth"],
            "bibliography": True,
        }
    )
    b = Requires.from_json(
        {"packages": ["ulem"], "fragments": ["ts-code"], "shell_escape": True, "index": [""]}
    )
    total = Requires.union([a, b])
    assert total.packages == ["booktabs", "glossaries", "ulem"]
    assert total.fragments == ["ts-glossary", "ts-code"]
    assert total.shell_escape is True and total.bibliography is True
    assert total.to_json()["citations"] == ["knuth"]

    state = apply_requires(
        DocumentState(),
        total,
        abbreviations=(
            model.AbbrDef(key="NMR", expansion="Nuclear Magnetic Resonance"),
            model.AbbrDef(key="GC-MS", expansion="unused"),
        ),
    )
    assert state.required_fragments == {"ts-glossary", "ts-code"}
    assert state.required_packages == ["booktabs", "ulem"]  # glossaries is ts-glossary's
    assert state.has_index_entries is True and state.index_registries == [""]
    assert state.requires_shell_escape is True
    assert state.citations == ["knuth"]
    assert state.acronyms == {"NMR": ("NMR", "Nuclear Magnetic Resonance")}
    assert required_fragment({"ts_required_fragments": ["ts-code"]}, "ts-code")
    assert not required_fragment({}, "ts-code")


def test_assets_emoji_and_scripts_passes_reach_the_tex(tmp_path: Path, monkeypatch) -> None:
    """The wave-3 passes on the CLI path: copied assets, emoji spans, script runs, the font summary."""
    from texsmith.adapters.transformers import register_converter, registry
    from texsmith.fonts.fallback import FallbackEntry, FallbackIndex, FallbackLookup
    from texsmith.fonts.scripts import ScriptDetector

    source = tmp_path / "doc.md"
    source.write_text(
        "# Passes\n\nHello 😀 world and Привет.\n\n![A figure](figure.png)\n\n"
        "```mermaid\n%% Pipeline\nflowchart LR\n  A --> B\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "figure.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    def fake_mermaid(diagram: str, *, output_dir: Path, **options: object) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        artefact = output_dir / "diagram.pdf"
        artefact.write_bytes(b"%PDF-1.4\n%fake\n")
        return artefact

    saved = registry.get("mermaid")
    register_converter("mermaid", fake_mermaid)
    cyrillic = FallbackEntry(
        name="Cyrillic", start=0x0400, end=0x04FF, group="Cyrillics", font={"name": "NotoSans"}
    )
    monkeypatch.setattr(
        ScriptDetector,
        "_ensure_lookup",
        lambda self: FallbackLookup(FallbackIndex([cyrillic])),  # noqa: ARG005
    )
    out = tmp_path / "out"
    try:
        _render([str(source), "-o", str(out), "-t", "article"])
    finally:
        register_converter("mermaid", saved)

    body = _body(out / "doc.tex")
    assert "\\tsemoji{😀}" in body
    assert "\\tsscript{cyrillics}{Привет}" in body
    assert "\\includegraphics[width=\\linewidth]{assets/figure.png}" in body
    assert (out / "assets" / "figure.png").is_file()
    assert "\\caption{Pipeline}" in body
    assert "{assets/diagram.pdf}" in body
    # The font summary of the ``scripts`` pass reached the ts-fonts provisioning.
    sty = (out / "ts-fonts.sty").read_text(encoding="utf-8")
    assert "\\textcyrillics" in sty


def _seed_doi_cache(output_dir: Path, doi: str, key: str) -> None:
    """Pre-fill the DOI cache the ``doi`` pass reads, so no network is touched."""
    import yaml

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = (
        f"@article{{{key},\n  author = {{Doe, Jane}},\n  title = {{Cached entry}},\n"
        f"  journal = {{J. Tests}},\n  year = {{2020}},\n  doi = {{{doi}}}\n}}\n"
    )
    (output_dir / "texsmith-doi-cache.yaml").write_text(
        yaml.safe_dump({"version": 1, "entries": {doi: payload}}), encoding="utf-8"
    )


def test_typst_bibliography_includes_the_doi_pass_entries(tmp_path: Path) -> None:
    """The ``.bib`` the Typst scaffolding cites carries the CLI entries and the fetched DOIs."""
    source = tmp_path / "doc.md"
    source.write_text(
        "---\ntitle: Cited\n---\n\n# Body\n\nSee @knuth84 and @doi:10.1000/cached.\n",
        encoding="utf-8",
    )
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@book{knuth84,\n  author = {Knuth, Donald},\n  title = {The TeXbook},\n"
        "  publisher = {Addison-Wesley},\n  year = {1984}\n}\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    _seed_doi_cache(out, "10.1000/cached", "Doe_2020")
    _render(
        [
            str(source),
            str(bib),
            "--format",
            "typst",
            "-t",
            "article",
            "-o",
            str(out),
        ]
    )
    typ = (out / "doc.typ").read_text(encoding="utf-8")
    assert "#cite(<knuth84>" in typ
    assert "#cite(<Doe_2020>" in typ
    assert '#bibliography("doc-refs.bib"' in typ
    refs = (out / "doc-refs.bib").read_text(encoding="utf-8")
    assert "knuth84" in refs
    assert "Doe_2020" in refs
    assert (out / "inline-doi-doc.bib").is_file()


def test_the_typst_backend_honours_the_request_it_is_given(tmp_path: Path) -> None:
    """``--hash-assets`` and ``--include-path`` reach the Typst passes.

    The entry point used to build a ``ConversionRequest`` of its own out of
    four arguments — template, bibliography, diagram backend, options — so
    every other field reverted to its default: assets were never hashed and
    the include search path was empty, which lost the included text outright
    while the LaTeX backend resolved it.
    """
    from texsmith.core.conversion import ConversionRequest
    from texsmith.core.conversion.typst import render_typst_document
    from texsmith.core.documents import Document

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "part.md").write_text("Included prose.\n", encoding="utf-8")
    (tmp_path / "figure.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    source = tmp_path / "doc.md"
    source.write_text(
        "# Passes\n\n![A figure](figure.png)\n\n{include}(part.md)\n", encoding="utf-8"
    )

    document = Document.from_markdown(source).prepare_for_conversion()
    typ = render_typst_document(
        document,
        ConversionRequest(hash_assets=True, include_paths=[elsewhere]),
        output_dir=tmp_path / "out",
    )

    assert "Included prose." in typ
    # ``hash_assets`` names an asset by the sha256 of its key, so the stored
    # name is a 64-hex digest rather than the source's own name.
    (asset,) = list((tmp_path / "out" / "assets").iterdir())
    assert asset.suffix == ".png"
    assert re.fullmatch(r"[0-9a-f]{64}", asset.stem), asset.name


def test_typst_assets_and_pass_values(tmp_path: Path, monkeypatch) -> None:
    """Diagrams become PNG for Typst, images land under assets/, the pass values reach the state."""
    from texsmith.adapters.transformers import register_converter, registry
    from texsmith.core.context import DocumentState
    from texsmith.core.conversion.typst import render_typst_document
    from texsmith.core.documents import Document
    from texsmith.fonts.fallback import FallbackEntry, FallbackIndex, FallbackLookup
    from texsmith.fonts.scripts import ScriptDetector

    source = tmp_path / "doc.md"
    source.write_text(
        "# Passes\n\nHello 😀 world and Привет.\n\n![A figure](figure.png)\n\n"
        "```mermaid\n%% Pipeline\nflowchart LR\n  A --> B\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "figure.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    formats: list[object] = []

    def fake_mermaid(diagram: str, *, output_dir: Path, **options: object) -> Path:
        formats.append(options.get("format"))
        output_dir.mkdir(parents=True, exist_ok=True)
        artefact = output_dir / "diagram.png"
        artefact.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return artefact

    saved = registry.get("mermaid")
    register_converter("mermaid", fake_mermaid)
    cyrillic = FallbackEntry(
        name="Cyrillic", start=0x0400, end=0x04FF, group="Cyrillics", font={"name": "NotoSans"}
    )
    monkeypatch.setattr(
        ScriptDetector,
        "_ensure_lookup",
        lambda self: FallbackLookup(FallbackIndex([cyrillic])),  # noqa: ARG005
    )
    out = tmp_path / "out"
    state = DocumentState()
    try:
        document = Document.from_markdown(source).prepare_for_conversion()
        typ = render_typst_document(
            document, ConversionRequest(template="article"), output_dir=out, state=state
        )
    finally:
        register_converter("mermaid", saved)

    assert formats == ["png"]
    assert 'image("assets/diagram.png")' in typ
    assert (out / "assets" / "diagram.png").is_file()
    assert 'image("assets/figure.png"' in typ
    assert (out / "assets" / "figure.png").is_file()
    assert "caption: [Pipeline]" in typ
    assert "#ts-emoji[😀]" in typ
    assert '#ts-script("cyrillics")[Привет]' in typ
    assert state.fonts_scanned is True
    assert any(entry.get("slug") == "cyrillics" for entry in state.script_usage)


# -- ResolveOptions.lang / --numbering (design 06 §Site-wide resolution) ----


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("french", "fr"),
        ("ngerman", "de"),
        ("german", "de"),
        ("english", "en"),
        ("british", "en"),
        ("italian", "it"),
        ("spanish", "es"),
        ("fr", "fr"),  # a tag passes through
        ("fr-CH", "fr"),  # as its primary subtag
        ("DE_de", "de"),
        ("klingon", None),  # unknown: tmark falls back to the front matter's ``lang``
        ("", None),
        (None, None),
    ],
)
def test_tmark_language_maps_babel_names_to_bcp47(name: str | None, expected: str | None) -> None:
    assert tmark_language(name) == expected


def test_numbering_mode_helpers() -> None:
    assert numbering_mode(None) == "backend"
    assert numbering_mode({}) == "backend"
    assert numbering_mode({NUMBERING_OVERRIDE_KEY: "tmark"}) == "tmark"
    assert numbering_mode({NUMBERING_OVERRIDE_KEY: " TMark "}) == "tmark"
    assert numbering_mode({NUMBERING_OVERRIDE_KEY: "nope"}) == "backend"
    # The first source naming a mode wins (context overrides, then the request's options).
    assert numbering_mode({}, {NUMBERING_OVERRIDE_KEY: "tmark"}) == "tmark"
    assert numbering_mode(None, {"other": 1}) == "backend"
    assert resolve_numbering("backend") is None
    assert resolve_numbering("tmark") == "all"
    assert writer_numbering("backend") is None
    assert writer_numbering("tmark") == dict.fromkeys(PREDECLARED_SERIES, "tmark")
    assert set(PREDECLARED_SERIES) >= {"fig", "tbl", "lst", "eq", "sec"}


def test_resolution_chain_options_carry_lang_and_numbering(tmp_path: Path) -> None:
    class _Doc:
        source_path = tmp_path / "doc.md"

    chain = ResolutionChain(lang="en", numbering="backend")
    default = chain.options_for(_Doc()).to_json()  # type: ignore[arg-type]
    assert default["lang"] == "en"
    assert "numbering" not in default
    explicit = chain.options_for(_Doc(), lang="fr", numbering="tmark").to_json()  # type: ignore[arg-type]
    assert explicit["lang"] == "fr"
    assert explicit["numbering"] == "all"


def _capture_resolve_options(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record the ``options`` every ``tmark.resolve`` of the run receives."""
    seen: list[dict[str, Any]] = []
    real = resolution.tmark.resolve

    def spy(doc: Any, loader: Any = None, options: Any = None, text: Any = None) -> Any:
        seen.append(dict(options or {}))
        return real(doc, loader, options, text)

    monkeypatch.setattr(resolution.tmark, "resolve", spy)
    return seen


def test_resolve_receives_the_resolved_language_on_both_backends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "rapport.md"
    source.write_text("---\nlanguage: french\n---\n# Bonjour\n\nTexte.\n", encoding="utf-8")
    seen = _capture_resolve_options(monkeypatch)
    _render([str(source), "-o", str(tmp_path / "tex")])
    _render([str(source), "--format", "typst", "-o", str(tmp_path / "typ")])
    assert [options["lang"] for options in seen] == ["fr", "fr"]
    assert all("numbering" not in options for options in seen)
    # ``--language`` wins over the front matter, as it does for babel.
    seen.clear()
    _render(["-l", "ngerman", str(source), "-o", str(tmp_path / "de")])
    assert seen[0]["lang"] == "de"


NUMBERED_FLOATS = """\
---
title: Floats
---
# Intro {#sec:intro}

See @tbl:one, @tbl:two and @sec:intro.

| a | b |
| - | - |
| 1 | 2 |

Table: First table {#tbl:one}

| c | d |
| - | - |
| 3 | 4 |

Table: Second table {#tbl:two}
"""


def test_numbering_tmark_prints_the_same_numbers_in_tex_and_typ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "floats.md"
    source.write_text(NUMBERED_FLOATS, encoding="utf-8")
    seen = _capture_resolve_options(monkeypatch)
    out = tmp_path / "out"
    _render(["--numbering", "tmark", str(source), "-o", str(out / "tex")])
    _render(
        [
            "--numbering",
            "tmark",
            "--format",
            "typst",
            str(source),
            "-o",
            str(out / "typ"),
        ]
    )
    assert [options["numbering"] for options in seen] == ["all", "all"]
    tex = (out / "tex" / "floats.tex").read_text(encoding="utf-8")
    typ = (out / "typ" / "floats.typ").read_text(encoding="utf-8")
    # tmark allocated the numbers at resolve time; both writers print them.
    assert "\\hyperref[tbl:one]{Table~1}" in tex
    assert "\\hyperref[tbl:two]{Table~2}" in tex
    assert "\\hyperref[sec:intro]{Section~1}" in tex
    assert "#link(<tbl:one>)[Table 1]" in typ
    assert "#link(<tbl:two>)[Table 2]" in typ
    assert "#link(<sec:intro>)[Section 1]" in typ
    # The default leaves the numbers to each backend.
    seen.clear()
    _render([str(source), "-o", str(out / "backend")])
    assert "numbering" not in seen[0]
    backend_tex = (out / "backend" / "floats.tex").read_text(encoding="utf-8")
    assert "Table~\\ref{tbl:one}" in backend_tex


_NUMBER = r"(?:FW|REQ)-\d+"


def _tex_numbers(body: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """``{key: number}`` of the definitions and ``[(key, number)]`` of the references."""
    definitions = dict(re.findall(rf"\\label\{{([a-z]+:[\w-]+)\}}({_NUMBER})", body))
    references = re.findall(rf"\\hyperref\[([a-z]+:[\w-]+)\]\{{({_NUMBER})\}}", body)
    return definitions, references


def _typ_numbers(text: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    definitions = {
        key: number for number, key in re.findall(rf"({_NUMBER})<([a-z]+:[\w-]+)>", text)
    }
    references = re.findall(rf"#link\(<([a-z]+:[\w-]+)>\)\[({_NUMBER})\]", text)
    return definitions, references


def test_counters_example_numbers_agree_across_backends_under_tmark_numbering(
    tmp_path: Path,
) -> None:
    source = EXAMPLES / "counters" / "counters.md"
    common = ["--numbering", "tmark", str(source)]
    _render([*common, "-o", str(tmp_path / "tex"), "-t", "article"])
    _render([*common, "--format", "typst", "-o", str(tmp_path / "typ")])
    tex_definitions, tex_references = _tex_numbers(_body(tmp_path / "tex" / "counters.tex"))
    typ_definitions, typ_references = _typ_numbers(
        (tmp_path / "typ" / "counters.typ").read_text(encoding="utf-8")
    )
    assert tex_definitions == typ_definitions
    assert tex_references == typ_references
    assert tex_definitions["fw:watchdog"] == "FW-01"
    assert tex_definitions["fw:rtc-drift"] == "FW-05"
    assert tex_definitions["req:watchdog-reset"] == "REQ-100"
    assert tex_definitions["req:log-retention"] == "REQ-103"
    assert ("fw:log-wrap", "FW-04") in tex_references  # the silent heading definition
    assert len(tex_references) >= 10


def test_numbering_option_is_validated() -> None:
    result = CliRunner().invoke(
        app,
        ["--numbering", "latex", str(EXAMPLES / "counters" / "counters.md")],
    )
    assert result.exit_code != 0
    assert "--numbering must be 'backend' or 'tmark'" in result.output
