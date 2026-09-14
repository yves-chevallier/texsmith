"""The pass framework: registry, ordering, ids, the pipeline runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from tmark.ir import model

from texsmith.core.documents import Document
from texsmith.passes import (
    DEFAULT_PIPELINE,
    IdAllocator,
    PassContext,
    PassOrderError,
    PassSpec,
    build_pipeline,
    run_pipeline,
)


def _noop(document: Document, ctx: PassContext) -> Document:
    del ctx
    return document


def test_default_pipeline_keeps_listed_order_and_stages() -> None:
    pipeline = build_pipeline()
    assert tuple(item.name for item in pipeline) == DEFAULT_PIPELINE
    stages = [item.stage for item in pipeline]
    assert stages == ["pre"] * 8 + ["post"] * 3
    assert stages.index("post") == len(DEFAULT_PIPELINE) - 3


def test_extra_pass_is_placed_after_its_dependency() -> None:
    extra = PassSpec(name="wordcount", run=_noop, after=("var",))
    names = [item.name for item in build_pipeline(extra=[extra])]
    assert names.index("wordcount") > names.index("var")
    # Listed order is stable: nothing else moved.
    assert [name for name in names if name != "wordcount"] == list(DEFAULT_PIPELINE)


def test_after_constraint_moves_a_listed_pass() -> None:
    first = PassSpec(name="a", run=_noop, after=("b",))
    second = PassSpec(name="b", run=_noop)
    ordered = build_pipeline(names=(), extra=[first, second])
    assert [item.name for item in ordered] == ["b", "a"]


def test_cycle_is_reported() -> None:
    a = PassSpec(name="a", run=_noop, after=("b",))
    b = PassSpec(name="b", run=_noop, after=("a",))
    with pytest.raises(PassOrderError, match="cycle"):
        build_pipeline(names=(), extra=[a, b])


def test_unknown_names_are_reported() -> None:
    with pytest.raises(PassOrderError, match="unknown pass 'nope'"):
        build_pipeline(names=("nope",))
    dangling = PassSpec(name="x", run=_noop, after=("ghost",))
    with pytest.raises(PassOrderError, match="unknown pass 'ghost'"):
        build_pipeline(names=(), extra=[dangling])


def test_pre_pass_cannot_follow_a_post_pass() -> None:
    late = PassSpec(name="late", run=_noop, after=("slots",))
    with pytest.raises(PassOrderError, match="post-resolve"):
        build_pipeline(extra=[late])


def test_id_allocator_floor_is_above_every_id() -> None:
    document = model.Document(
        blocks=(
            model.Para(content=(model.Str(text="a", id=7),), id=3),
            model.Header(level=1, content=(), id=42),
        ),
        footnotes=(model.Footnote(label="n", content=(), id=99),),
    )
    ids = IdAllocator()
    ids.observe(document)
    assert ids.floor == 100
    assert ids.next() == 100
    assert ids.reserve(3) == 101
    assert ids.next() == 104
    ids.observe(model.Str(text="x", id=5))
    assert ids.floor == 105


def test_run_pipeline_runs_resolve_between_stages(harness) -> None:
    document = harness.load("stubs", "plain")
    ctx = harness.context(document)
    order: list[str] = []

    def record(name: str, stage: str) -> PassSpec:
        def run(doc: Document, _ctx: PassContext) -> Document:
            order.append(name)
            return doc

        return PassSpec(name=name, run=run, stage=stage)  # type: ignore[arg-type]

    def resolve(doc: Document, _ctx: PassContext) -> Document:
        order.append("resolve")
        return doc.evolve(resolved={"next_start": {}})

    pipeline = (record("one", "pre"), record("two", "post"))
    out = run_pipeline(document, ctx, pipeline, resolve=resolve)
    assert order == ["one", "resolve", "two"]
    assert out.resolved == {"next_start": {}}
    assert document.resolved is None  # the input is never mutated


def test_the_ir_and_the_diagnostics_share_one_span() -> None:
    """One definition: it is generated from tmark's schema and imported here."""
    from texsmith.diagnostics.model import NO_SPAN as DIAG_NO_SPAN, Span as DiagSpan

    assert model.Span is DiagSpan
    assert model.NO_SPAN is DIAG_NO_SPAN
    assert model.Span(2, 10, 20).to_json() == [2, 10, 20]


def test_fixture_inputs_are_fresh() -> None:
    """The committed ``.in.json`` files match the installed wheel (``make ir-fixtures``)."""
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[2] / "scripts" / "refresh_pass_fixtures.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# The id and span rules (``texsmith.passes`` docstring)
# ---------------------------------------------------------------------------


def _cases() -> list[tuple[str, str]]:
    """Every committed pass fixture, as ``(pass, case)``."""
    root = Path(__file__).resolve().parent
    return sorted(
        (path.parent.name, path.name.removesuffix(".in.json"))
        for path in root.glob("*/*.in.json")
        if path.parent.name != "stubs"  # shared inputs, not a pass of their own
    )


@pytest.mark.parametrize(("pass_name", "case"), _cases(), ids=lambda v: v)
def test_a_pass_never_mints_an_id_twice(harness, pass_name: str, case: str) -> None:
    """Rule 2: a synthesised node takes a *fresh* id, never the source's.

    Two nodes at one address is not a visible failure — it is a resolution that
    silently attaches to the wrong one. Nothing enforced this: the rule was
    cited by number in three docstrings and written down in none.
    """
    from collections import Counter

    from tmark.ir.walk import walk

    document = harness.load(pass_name, case)
    ctx = harness.context(document)
    out = harness.run(pass_name, document, ctx)
    if out.ir is None:
        pytest.skip("the pass produced no IR")
    ids = [node.id for node in walk(out.ir) if getattr(node, "id", None) is not None]
    duplicated = sorted(value for value, count in Counter(ids).items() if count > 1)
    assert not duplicated, f"{pass_name}/{case}: ids used twice: {duplicated[:5]}"


@pytest.mark.parametrize(("pass_name", "case"), _cases(), ids=lambda v: v)
def test_a_pass_never_leaves_a_span_on_an_unregistered_file(
    harness, pass_name: str, case: str
) -> None:
    """Rules 1 and 2: a span is the author's location, so its file must exist.

    A span carrying a file id the ``FileTable`` never registered renders
    without a path, or with another document's — the bug class step 03 found
    twice, the snippet fence that named its host page.
    """
    from tmark.ir.walk import walk

    document = harness.load(pass_name, case)
    ctx = harness.context(document)
    out = harness.run(pass_name, document, ctx)
    if out.ir is None:
        pytest.skip("the pass produced no IR")
    registered = set(range(len(ctx.files)))
    used = {node.span.file for node in walk(out.ir) if getattr(node, "span", None) is not None}
    assert used <= registered, (
        f"{pass_name}/{case}: spans name unregistered files {sorted(used - registered)}"
    )
