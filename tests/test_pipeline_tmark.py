"""The IR path end to end: ``--reader tmark`` on the examples (no PDF build).

The bodies come from ``tmark.write``; the template wrapping is the legacy
one. The ``ts-*`` contract macros (``\\tsacr``, ``\\tscodeinline``, …) are
asserted in the written ``.tex``; whether the fragments define them is the
engine's business and is not run here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from texsmith.core.context import DocumentState
from texsmith.core.conversion import ConversionRequest
from texsmith.core.conversion.bodies import Requires, build_writer_options
from texsmith.core.conversion.resolution import ResolutionChain, bibliography_paths
from texsmith.core.conversion.service import ConversionService
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
            "--reader",
            "tmark",
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
            "--reader",
            "tmark",
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
    assert "\\tscodeinline{counters:}" in body
    assert "\\begin{tabularx}" in body
    # Undeclared prefixes survive verbatim.
    assert "node.id" in body


def test_code_example_highlights_through_the_pass(tmp_path: Path) -> None:
    out = tmp_path / "code"
    _render(
        [
            "--reader",
            "tmark",
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
            "--reader",
            "tmark",
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
            "--reader",
            "tmark",
            str(EXAMPLES / "snippet" / "docs" / "index.md"),
            "-o",
            str(out),
            "-t",
            "article",
        ]
    )
    body = _body(out / "index.tex")
    # Both fences (one nested in a four-backtick fence) became figures with
    # the caption and the width the info string carried; the previews sit in
    # ``snippets/`` next to the ``.tex``.
    assert seen == [
        "Hello **World**!",
        '```c\n#include <stdio.h>\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}\n```',
    ]
    assert body.count("\\begin{figure}") == 2
    assert body.count("\\includegraphics[width=0.8\\linewidth]{snippets/snippet-") == 2
    assert body.count("\\caption[Demo]{Demo}") == 2
    assert "\\begin{tscode}" not in body and "Hello **World**" not in body
    previews = sorted((out / "snippets").glob("snippet-*.pdf"))
    assert len(previews) == 2
    for preview in previews:
        assert f"{{snippets/{preview.name}}}" in body


def test_snippet_example_typst_takes_the_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_snippet_renderer(monkeypatch)
    out = tmp_path / "snippet-typst"
    _render(
        [
            "--reader",
            "tmark",
            str(EXAMPLES / "snippet" / "docs" / "index.md"),
            "--format",
            "typst",
            "-o",
            str(out),
        ]
    )
    typ = (out / "index.typ").read_text(encoding="utf-8")
    assert typ.count('image("snippets/snippet-') == 2
    assert '.png", width: 80%)' in typ
    assert "caption: [Demo]" in typ


def test_typst_hello_example_writes_a_typst_body(tmp_path: Path) -> None:
    out = tmp_path / "hello"
    _render(
        [
            "--reader",
            "tmark",
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
            "--reader",
            "tmark",
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


def test_debug_html_dumps_the_ir(tmp_path: Path) -> None:
    out = tmp_path / "dbg"
    _render(
        [
            "--reader",
            "tmark",
            "--debug-html",
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
    assert not (out / "abbreviations.debug.html").exists()


def test_html_reader_stays_the_default(tmp_path: Path) -> None:
    out = tmp_path / "legacy"
    _render([str(EXAMPLES / "abbr" / "abbreviations.md"), "-o", str(out), "-t", "article"])
    body = _body(out / "abbreviations.tex")
    assert "\\acrshort{NMR}" in body
    assert "\\tsacr{" not in body


def test_html_output_rejects_the_tmark_reader() -> None:
    result = CliRunner().invoke(
        app, ["--reader", "tmark", "--html", str(EXAMPLES / "abbr" / "abbreviations.md")]
    )
    assert result.exit_code != 0
    assert "--html needs the html reader" in result.output


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
        reader="tmark",
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
