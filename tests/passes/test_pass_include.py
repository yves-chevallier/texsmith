"""The ``include`` pass: splicing, rebasing, definitions, fence includes, failures."""

from __future__ import annotations

from pathlib import Path

from tmark.ir import model
from tmark.ir.walk import plain_text, walk

from texsmith.passes.include import rebase_path, shift_ids
from texsmith.readers.loader import MemoryLoader


FIXTURES = Path(__file__).resolve().parent
PARTS = FIXTURES / "include" / "parts"
SHARED = FIXTURES / "include" / "shared"


def _loader() -> MemoryLoader:
    """Every file under ``parts/`` keyed by the path ``loader.join`` computes."""
    files = {str(path): path.read_text("utf-8") for path in PARTS.rglob("*") if path.is_file()}
    files[str(FIXTURES / "include" / "cycle.md")] = (FIXTURES / "include" / "cycle.md").read_text(
        "utf-8"
    )
    return MemoryLoader(files)


def _search_loader() -> MemoryLoader:
    """``parts/`` beside the document plus ``shared/``, the search path's directory."""
    files = {str(path): path.read_text("utf-8") for path in PARTS.rglob("*") if path.is_file()}
    files.update(
        {str(path): path.read_text("utf-8") for path in SHARED.rglob("*") if path.is_file()}
    )
    return MemoryLoader(files)


def test_rebase_path() -> None:
    assert rebase_path("img/fig.png", "parts") == "parts/img/fig.png"
    assert rebase_path("../assets/n.svg", "parts") == "assets/n.svg"
    assert rebase_path("../x.png", "..") == "../../x.png"
    assert rebase_path("fig.png", ".") == "fig.png"
    assert rebase_path("https://example.org/r.png", "parts") == "https://example.org/r.png"
    assert rebase_path("/abs/root.png", "parts") == "/abs/root.png"
    assert rebase_path("", "parts") == ""


def test_shift_ids_moves_node_and_record_ids_only() -> None:
    doc = model.Document(
        blocks=(model.Para(content=(model.Str(text="x", id=2),), id=1),),
        footnotes=(model.Footnote(label="n", content=(model.Para(id=4),), id=3),),
        abbreviations=(model.AbbrDef(key="A", expansion="a", id=5),),
    )
    shifted = shift_ids(doc, 100)
    assert [node.id for node in walk(shifted)] == [101, 102, 104]
    assert shifted.footnotes[0].id == 103
    assert shifted.abbreviations[0].id == 105
    header = model.Header(level=1, attrs=model.Attrs(id="sec:x"), id=7)
    assert shift_ids(header, 10).attrs.id == "sec:x"


def test_includes_are_spliced_rebased_and_merged(harness) -> None:
    document = harness.load("include", "basic")
    ctx = harness.context(document, loader=_loader())
    floor = ctx.ids.floor
    out = harness.run("include", document, ctx)

    assert out is not document and out.ir is not None and document.ir is not None
    assert not [node for node in walk(out.ir) if isinstance(node, model.Include)]
    headers = [
        (block.level, plain_text(block.content))
        for block in out.ir.blocks
        if isinstance(block, model.Header)
    ]
    assert headers == [(1, "Main"), (2, "Chapter"), (3, "Nested")]

    # Relative paths of the included files point from the main document's directory.
    images = {
        plain_text(node.alt): node.src for node in walk(out.ir) if isinstance(node, model.Image)
    }
    assert images == {
        "Fig": "parts/img/fig.png",
        "Nested": "assets/n.svg",
        "Remote": "https://example.org/r.png",
        "Root": "/abs/root.png",
        "L": "parts/deep/l.png",
        "inline": "parts/img/note.png",
    }

    # Fence includes take the file's text (from the file the fence sits in) and lose the option.
    codes = [node for node in walk(out.ir) if isinstance(node, model.CodeBlock)]
    assert [code.text for code in codes] == [
        'print("nested")\n',
        "def hanoi(n):\n    return 2**n - 1\n",
        "[include: parts/absent.py not found]",
    ]
    assert all("include" not in dict(code.options.kv) for code in codes)

    # Definitions of the included file join the host's; ids are unique and above the old floor.
    assert [note.label for note in out.ir.footnotes] == ["main", "ch"]
    assert [abbr.key for abbr in out.ir.abbreviations] == ["HTML"]
    ids = [node.id for node in walk(out.ir)]
    assert len(ids) == len(set(ids))
    old_ids = {node.id for node in walk(document.ir)}
    new_ids = [node.id for node in walk(out.ir) if node.span.file != 0]
    assert new_ids and all(floor <= value < ctx.ids.floor for value in new_ids)
    assert not old_ids & set(new_ids)

    # Spans keep the included file's id; the files are registered in inclusion order.
    assert [Path(ctx.files.path(i)).name for i in ctx.files] == [
        "basic.md",
        "chapter.md",
        "nested.md",
        "leaf.md",
    ]
    chapter = next(b for b in out.ir.blocks if isinstance(b, model.Header) and b.level == 2)
    assert chapter.span.file == 1
    nested = next(b for b in out.ir.blocks if isinstance(b, model.Header) and b.level == 3)
    assert nested.span.file == 2

    # A missing file is a visible literal at the include's span, reported once.
    literal = next(
        node
        for node in walk(out.ir)
        if isinstance(node, model.Str) and node.text == "[include: missing.md not found]"
    )
    assert literal.span.file == 0
    assert harness.diagnostics(ctx) == harness.expected_diagnostics("include", "basic")
    assert harness.structural(out) == harness.expected("include", "basic")


def test_cycle_is_cut_with_a_diagnostic(harness) -> None:
    document = harness.load("include", "cycle")
    ctx = harness.context(document, loader=_loader())
    out = harness.run("include", document, ctx)
    assert out.ir is not None
    texts = [plain_text(b.content) for b in out.ir.blocks if isinstance(b, model.Para)]
    assert texts == ["Loop text.", "[include: ../cycle.md skipped, cycle]"]
    assert [record.code for record in ctx.diagnostics] == ["include-cycle"]
    assert ctx.diagnostics.sorted()[0].span.file == 1  # reported in loop.md
    assert harness.structural(out) == harness.expected("include", "cycle")


def test_pass_is_identity_without_includes(harness) -> None:
    document = harness.load("stubs", "plain")
    ctx = harness.context(document)
    assert harness.run("include", document, ctx) is document
    assert len(ctx.diagnostics) == 0


def test_search_path_catches_what_the_document_directory_misses(harness) -> None:
    document = harness.load("include", "search")
    ctx = harness.context(document, loader=_search_loader(), include_paths=(SHARED,))
    out = harness.run("include", document, ctx)
    assert out.ir is not None

    # A path that resolves beside the document is read there (the spec's rule),
    # one that does not is looked up in the search path.
    headers = [
        (block.level, plain_text(block.content))
        for block in out.ir.blocks
        if isinstance(block, model.Header)
    ]
    assert headers == [(1, "Search"), (2, "Near"), (2, "Far")]

    # The file actually read is the one registered, so a diagnostic names it.
    assert [Path(ctx.files.path(index)) for index in ctx.files] == [
        FIXTURES / "include" / "search.md",
        PARTS / "near.md",
        SHARED / "far.md",
    ]

    # The fence form has the same provenance and the same fallback.
    codes = [node for node in walk(out.ir) if isinstance(node, model.CodeBlock)]
    assert [code.text for code in codes] == ['print("far")\n']
    assert all("include" not in dict(code.options.kv) for code in codes)

    # A file no directory holds keeps the visible literal and the diagnostic.
    literals = [
        node.text
        for node in walk(out.ir)
        if isinstance(node, model.Str) and node.text.startswith("[include:")
    ]
    assert literals == ["[include: nowhere.md not found]"]
    assert [record.code for record in ctx.diagnostics] == ["include-missing"]


def test_without_a_search_path_only_the_document_directory_counts(harness) -> None:
    document = harness.load("include", "search")
    ctx = harness.context(document, loader=_search_loader())
    out = harness.run("include", document, ctx)
    assert out.ir is not None

    headers = [
        (block.level, plain_text(block.content))
        for block in out.ir.blocks
        if isinstance(block, model.Header)
    ]
    assert headers == [(1, "Search"), (2, "Near")]
    literals = [
        node.text
        for node in walk(out.ir)
        if isinstance(node, model.Str) and node.text.startswith("[include:")
    ]
    assert literals == ["[include: far.md not found]", "[include: nowhere.md not found]"]
    codes = [node for node in walk(out.ir) if isinstance(node, model.CodeBlock)]
    assert [code.text for code in codes] == ["[include: far-snippet.py not found]"]
    assert [record.code for record in ctx.diagnostics] == ["include-missing"] * 3
