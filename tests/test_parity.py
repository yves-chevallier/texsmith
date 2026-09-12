"""Unit tests for the regression harness (scripts/parity.py): normaliser, diffing, gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import textwrap

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "parity.py"


@pytest.fixture(scope="module")
def parity():
    spec = importlib.util.spec_from_file_location("parity_harness", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------ comments


def test_find_comment_skips_escaped_percent(parity):
    assert parity.find_comment(r"100\% sure % really") == 11
    assert parity.find_comment(r"no comment here \%") == -1
    assert parity.find_comment(r"\\% a comment after an escaped backslash") == 2
    assert parity.find_comment("% column zero") == 0


def test_strip_tex_comments_outside_verbatim_only(parity):
    text = textwrap.dedent(
        r"""
        % a leading comment
        \section{A} % trailing
        \begin{minted}{python}
        # not a TeX comment: 50% of the time
        x = 1 % kept verbatim
        \end{minted}
        \begin{tscode}
        keep % this
        \end{tscode}
        after % gone
        """
    )
    result = parity.strip_tex_comments(text)
    assert "leading comment" not in result
    assert "\\section{A}" in result and "trailing" not in result
    assert "50% of the time" in result
    assert "x = 1 % kept verbatim" in result
    assert "keep % this" in result
    assert "after" in result and "gone" not in result


def test_strip_tex_comments_nested_environment_stack(parity):
    text = "\\begin{code}\n\\begin{itemize}\n% inside\n\\end{itemize}\n\\end{code}\n% outside\n"
    result = parity.strip_tex_comments(text)
    assert "% inside" in result
    assert "% outside" not in result


# -------------------------------------------------------------- normalise


def test_collapse_blank_lines(parity):
    assert parity.collapse_blank_lines("\n\na  \n\n\n\nb\t\n\n") == "a\n\nb\n"


def test_normalise_tex_rules(parity):
    text = textwrap.dedent(
        r"""
        \providecommand{\tslead}[1]{\textbf{#1}}
        \includegraphics[width=\linewidth]{assets/1fd2a36affb926e899f2c771fe25b09a36ac52a37a3a51ff3af7ec45c5f77464.pdf}
        \includegraphics{assets/.converted/sample.pdf}
        \includegraphics{assets/remote/photo.jpg}
        \addbibresource{inline-doi-cheese.bib}
        \input{cheese.tex}
        Text about cheese.
        """
    )
    result = parity.normalise_tex(text, stems=("cheese",))
    assert "tslead" not in result
    assert "{<HASH>.pdf}" in result
    assert "{sample.pdf}" in result
    assert "{photo.jpg}" in result
    assert "inline-doi-<STEM>.bib" in result
    assert "\\input{<STEM>.tex}" in result
    assert "Text about cheese." in result  # prose is untouched
    assert result.endswith(".\n")


def test_normalise_typ_rules(parity):
    text = textwrap.dedent(
        """
        #import "@preview/mitex:0.2.6": *
        // a comment line
        #set text(size: 11pt)


        #image("assets/1fd2a36affb926e899f2c771fe25b09a36ac52a37a3a51ff3af7ec45c5f77464.png")
        #image("assets/sub/photo.png", width: 50%)
        #bibliography("cheese.bib")
        """
    )
    result = parity.normalise_typ(text, stems=("cheese",))
    assert "mitex" not in result
    assert "// a comment" not in result
    assert '#image("<HASH>.png")' in result
    assert '#image("photo.png", width: 50%)' in result
    assert '#bibliography("<STEM>.bib")' in result
    assert "\n\n\n" not in result


def test_strip_typst_prelude_drops_only_the_contract_bindings(parity):
    text = textwrap.dedent(
        """
        #let ts-callout-colors = (
          note: (bg: rgb("ecf3ff"), frame: rgb("448aff")),
        )
        #let ts-mark(body) = highlight(body)
        #let ts-logo(name) = {
          if name == "TeX" { ts-tex } else { name }
        }
        #let mine = 1
        A paragraph mentioning ts-mark in prose.
        """
    )
    result = parity.strip_typst_prelude(text)
    assert "ts-callout-colors" not in result
    assert "rgb(" not in result
    assert "#let ts-mark" not in result
    assert "#let ts-logo" not in result
    assert 'if name == "TeX"' not in result
    assert "#let mine = 1" in result  # only the `ts-` contract bindings go
    assert "A paragraph mentioning ts-mark in prose." in result


def test_strip_typst_prelude_keeps_a_raw_fence(parity):
    text = "```typ\n#let ts-mark(body) = highlight(body)\n```\n"
    assert parity.strip_typst_prelude(text) == text


def test_tidy_typ_layout_closes_a_fence_that_carries_a_bracket(parity):
    text = textwrap.dedent(
        """
        #ts-code(linenums: 1)[
        ```python
            indented = 1
        ```]
            after the fence
        """
    )
    result = parity.tidy_typ_layout(text)
    assert "    indented = 1" in result  # inside the fence: indentation kept
    assert "\nafter the fence" in result  # outside: indentation dropped


def test_tidy_typ_layout_trims_a_content_block(parity):
    text = '#ts-callout(kind: "note")[\n\nBody.\n\n]\n'
    assert parity.tidy_typ_layout(text) == '#ts-callout(kind: "note")[\nBody.]\n'


def test_tidy_tex_layout_splits_a_heading_label(parity):
    text = "\\section{Intro}\\label{intro}\n\\caption{Fig}\\label{fig}\n"
    result = parity.tidy_tex_layout(text)
    assert result.startswith("\\section{Intro}\n\\label{intro}\n")
    assert "\\caption{Fig}\\label{fig}" in result  # a float label is never split


def test_tidy_tex_layout_drops_a_blank_next_to_page_furniture(parity):
    text = "\\tsreplayfn\n\n\\thispagestyle{plain}\n\\section{A}\n"
    assert "\n\n" not in parity.tidy_tex_layout(text)


# --------------------------------------------------------------- diffing


def test_compare_texts_reports_every_hunk(parity):
    old = "\\item{} one\nsame\nText \\marginnote{aside}.\n"
    new = "\\item one\nsame\nText\\marginnote{aside}.\n"

    verdict = parity.compare_texts(old, new, relpath="docs/syntax/notes/notes.tex")
    assert verdict.status == parity.DIFFERS
    assert verdict.hunks == 2  # there is no allow-list: both differences count
    assert "item" in verdict.diff and "marginnote" in verdict.diff


def test_compare_texts_identical(parity):
    verdict = parity.compare_texts("a\nb\n", "a\nb\n", relpath="x/x.tex")
    assert verdict.status == parity.IDENTICAL
    assert verdict.hunks == 0
    assert verdict.diff == ""


def test_split_hunks_counts(parity):
    hunks = parity.split_hunks("a\nb\nc\nd\n", "a\nB\nc\nD\n")
    assert len(hunks) == 2
    assert hunks[0].text == "-b\n+B"


# ----------------------------------------------------------------- corpus


def test_corpus_loads_and_is_well_formed(parity):
    entries = parity.load_corpus()
    ids = [e.entry_id for e in entries]
    assert len(ids) == len(set(ids))
    assert "abbr" in ids and "abbr@typst" in ids
    assert "docs/syntax/tables" in ids and "docs/syntax/tables@typst" in ids
    assert not any(e.entry_id.startswith(("mkdocs", "recipe")) for e in entries)
    for entry in entries:
        assert "--build" not in entry.args
        assert entry.requires <= parity.KNOWN_REQUIREMENTS
        if entry.backend == "typst":
            assert "--format" in entry.args and "typst" in entry.requires
    docs = [e for e in entries if e.entry_id.startswith("docs/")]
    assert len(docs) == 2 * len(sorted(parity.ROOT.glob("docs/**/*.md")))


def test_entry_command_and_stems(parity):
    entry = parity.Entry(
        "paper", "examples/paper", ("cheese.md", "cheese.bib", "-tarticle"), "latex"
    )
    assert entry.stems == ("cheese", "main")
    multi = parity.Entry(
        "multi", "examples/multi-document", ("a.md", "b.md", "config.yml"), "latex"
    )
    assert multi.stems == ("main",)
    assert entry.command(out_dir=Path("/o")) == [
        "cheese.md",
        "cheese.bib",
        "-tarticle",
        "-o",
        "/o",
    ]
    # The CLI has one reader and no ``--reader`` option: no flag is ever passed.
    assert entry.command(out_dir=Path("/o"), build=True)[-3:] == [
        "-o",
        "/o",
        "--build",
    ]


def _pdf_with_text(path: Path, pages: list[str]) -> Path:
    import fitz

    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=24)
    doc.save(path)
    doc.close()
    return path


def test_missing_requirements_honours_without(parity):
    entry = parity.Entry("x", ".", ("x.md",), "latex", frozenset({"docker", "typst"}))
    assert "docker" in parity.missing_requirements(entry, without=["docker"])
    assert "docker" not in parity.missing_requirements(entry, without=["docker"], ignore=["docker"])


# ------------------------------------------------------------ subcommand wiring


def test_the_harness_pins_no_reader(parity):
    """One reader, no flag: neither subcommand takes one, and nothing is passed."""
    args = parity.build_parser().parse_args(["render", "--out", "x"])
    assert not hasattr(args, "reader")
    assert parity.build_parser().parse_args(["baseline", "--check"]).check
    assert not any(name.endswith("READER") or name == "READERS" for name in vars(parity))


def test_the_diff_subcommand_is_gone(parity, capsys):
    """It compared two readers; there is only one left, so it cannot run."""
    with pytest.raises(SystemExit):
        parity.build_parser().parse_args(["diff"])
    assert "invalid choice" in capsys.readouterr().err


def test_pdf_needs_baseline(parity, capsys):
    """`pdf` builds against the committed record or not at all."""
    assert parity.main(["pdf", "--entries", "abbr"]) == 2
    assert "--baseline" in capsys.readouterr().err
    assert parity.main(["pdf", "--check", "--entries", "abbr"]) == 2
    assert "--baseline" in capsys.readouterr().err


def test_pdf_baseline_has_a_default_entry_set(parity):
    args = parity.build_parser().parse_args(["pdf", "--baseline"])
    assert args.entries is None
    corpus = {entry.entry_id: entry for entry in parity.load_corpus()}
    assert [e.entry_id for e in parity._pdf_baseline_entries(args, corpus)] == list(
        parity.PDF_BASELINE_ENTRIES
    )


# ---------------------------------------------------------------- pdf baseline


def test_page_text_collapses_whitespace(parity):
    assert parity.page_text("  a\n b \t c \n\n") == "a b c"


def test_pdf_digest_records_text_size_and_ink(parity, tmp_path):
    pdf = _pdf_with_text(tmp_path / "one.pdf", ["Hello parity", "page two"])
    pages = parity.pdf_digest(pdf, dpi=50)
    assert [p["text"] for p in pages] == ["Hello parity", "page two"]
    assert all(p["size"] == pages[0]["size"] for p in pages)
    assert 0 < pages[0]["ink"] < 0.1
    # Same input, same record: the digest is what gets committed.
    assert (
        parity.pdf_digest(_pdf_with_text(tmp_path / "two.pdf", ["Hello parity"]), dpi=50)[0]
        == (pages[0])
    )


def test_compare_pdf_digest(parity):
    recorded = [{"size": [100, 200], "ink": 0.01, "text": "Hello"}]
    assert parity.compare_pdf_digest(recorded, recorded)[0] == parity.IDENTICAL

    status, detail = parity.compare_pdf_digest(recorded, recorded * 2)
    assert status == parity.DIFFERS and "page count 1 vs 2" in detail

    status, detail = parity.compare_pdf_digest(recorded, [{**recorded[0], "text": "Goodbye"}])
    assert status == parity.DIFFERS and "text layer changed" in detail

    status, detail = parity.compare_pdf_digest(recorded, [{**recorded[0], "size": [100, 300]}])
    assert status == parity.DIFFERS and "raster" in detail

    # Ink moves within the tolerance (antialiasing, a font metric) and is let through…
    nudged = {**recorded[0], "ink": 0.01 + parity.INK_TOLERANCE / 2}
    assert parity.compare_pdf_digest(recorded, [nudged])[0] == parity.IDENTICAL
    # …beyond it, it is a finding.
    moved = {**recorded[0], "ink": 0.01 + parity.INK_TOLERANCE * 2}
    status, detail = parity.compare_pdf_digest(recorded, [moved])
    assert status == parity.DIFFERS and "ink" in detail


def test_committed_pdf_baseline_is_well_formed(parity):
    import json

    payload = json.loads(parity.PDF_BASELINE_PATH.read_text(encoding="utf-8"))
    assert payload["dpi"] == parity.build_parser().parse_args(["pdf", "--baseline"]).dpi
    documents = payload["documents"]
    assert {name.split("/")[0] for name in documents} == set(parity.PDF_BASELINE_ENTRIES)
    for pages in documents.values():
        assert pages and all({"size", "ink", "text"} == set(page) for page in pages)
