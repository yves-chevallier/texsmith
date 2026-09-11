"""The IR path end to end: ``--reader tmark`` on the examples (no PDF build).

The bodies come from ``tmark.write``; the template wrapping is the legacy
one. The ``ts-*`` contract macros (``\\tsacr``, ``\\tscodeinline``, …) are
asserted in the written ``.tex``; whether the fragments define them is the
engine's business and is not run here.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    assert "\\section{Scope}\\label{scope}" in body
    assert "\\subsection{Summary}\\label{summary}" in body
    assert "\\label{fw:watchdog}FW-01" in body
    assert "\\label{req:log-retention}REQ-103" in body
    assert "\\hyperref[fw:watchdog]{FW-01}" in body
    assert "\\tscodeinline{counters:}" in body
    assert "\\begin{tabularx}" in body
    # Undeclared prefixes survive verbatim.
    assert "node.id" in body


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
    assert "= Hello Typst <hello-typst>" in typ
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
    assert "= Hello Typst <hello-typst>" in typ
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
